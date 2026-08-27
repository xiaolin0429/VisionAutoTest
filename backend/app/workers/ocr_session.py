from __future__ import annotations

import hashlib
import json
import math
import struct
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from app.workers.ocr_engine import OcrEngineError
from app.workers.ocr_evidence import (
    DEFAULT_MAX_CANDIDATE_SUMMARIES,
    DEFAULT_MAX_TEXT_LENGTH,
    HARD_MAX_CANDIDATE_SUMMARIES,
    HARD_MAX_TEXT_LENGTH,
    OcrEvidenceCacheSnapshot,
    OcrEvidenceCapture,
    OcrResolutionEvidence,
)
from app.workers.ocr_page import (
    OcrPageGeometryError,
    build_ocr_page_snapshot_from_analysis,
)
from app.workers.ocr_targeting import (
    OcrTargetingError,
    normalize_ocr_text,
    resolve_ocr_target,
)
from app.workers.ocr_types import (
    OcrElementRelation,
    OcrErrorCode,
    OcrLanguageProfile,
    OcrPageSnapshot,
    OcrPreprocessingProfile,
    OcrRect,
    OcrTargetCandidate,
    OcrTargetResolution,
    OcrTargetSpec,
    OcrTextBlock,
    OcrTextElement,
    OcrTextLine,
)

_READ_PAGE_GEOMETRY_SCRIPT = """
() => {
  const root = document.scrollingElement || document.documentElement;
  return {
    scroll_x: Number(window.scrollX || root.scrollLeft || 0),
    scroll_y: Number(window.scrollY || root.scrollTop || 0),
    scroll_width: Number(Math.max(root.scrollWidth, window.innerWidth)),
    scroll_height: Number(Math.max(root.scrollHeight, window.innerHeight)),
    viewport_width: Number(window.innerWidth),
    viewport_height: Number(window.innerHeight)
  };
}
"""

_SCROLL_PAGE_SCRIPT = """
position => {
  window.scrollTo(position.x, position.y);
}
"""

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_DEFAULT_CACHE_MEMORY_BYTES = 64 * 1024 * 1024
_DEFAULT_CACHE_MAX_ENTRIES = 64
_DEFAULT_CACHE_TTL_SECONDS = 30.0
_DEFAULT_TOTAL_TIMEOUT_SECONDS = 15.0

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class OcrPageLike(Protocol):
    url: str

    def screenshot(self, **kwargs: object) -> bytes: ...

    def evaluate(self, expression: str, arg: object | None = None) -> object: ...

    def wait_for_timeout(self, timeout_ms: float) -> None: ...


class OcrAnalyzer(Protocol):
    def analyze_ocr(
        self,
        *,
        image_png_bytes: bytes,
        language_profile: OcrLanguageProfile | None = None,
    ) -> Mapping[str, object]: ...


class ScreenshotProvider(Protocol):
    def capture(self, page: OcrPageLike) -> bytes: ...


class PlaywrightViewportScreenshotProvider:
    def capture(self, page: OcrPageLike) -> bytes:
        return page.screenshot(
            type="png",
            full_page=False,
            scale="css",
            animations="disabled",
            caret="hide",
        )


@dataclass(frozen=True, slots=True)
class PageScrollGeometry:
    scroll_x: float
    scroll_y: float
    scroll_width: float
    scroll_height: float
    viewport_width: int
    viewport_height: int


@dataclass(frozen=True, slots=True)
class OcrSessionCacheStats:
    analysis_hits: int
    analysis_misses: int
    snapshot_hits: int
    snapshot_misses: int
    analysis_entries: int
    snapshot_entries: int
    estimated_bytes: int
    generation: int
    navigation_epoch: int
    last_invalidation_reason: str | None


@dataclass(frozen=True, slots=True)
class _AnalysisCacheKey:
    navigation_epoch: int
    generation: int
    url: str
    viewport_width: int
    viewport_height: int
    screenshot_checksum_sha256: str
    language_profile: OcrLanguageProfile
    preprocessing_profile: OcrPreprocessingProfile


@dataclass(frozen=True, slots=True)
class _SnapshotCacheKey:
    navigation_epoch: int
    generation: int
    url: str
    viewport_width: int
    viewport_height: int
    scroll_x: float
    scroll_y: float
    screenshot_checksum_sha256: str
    language_profile: OcrLanguageProfile
    preprocessing_profile: OcrPreprocessingProfile


@dataclass(slots=True)
class _CacheEntry(Generic[V]):
    value: V
    estimated_bytes: int
    expires_at: float


class _TtlLruCache(Generic[K, V]):
    def __init__(
        self,
        *,
        max_entries: int,
        max_bytes: int,
        ttl_seconds: float,
        clock: Callable[[], float],
    ) -> None:
        if max_entries < 1:
            raise ValueError("OCR cache max_entries must be positive.")
        if max_bytes < 1:
            raise ValueError("OCR cache max_bytes must be positive.")
        if ttl_seconds <= 0:
            raise ValueError("OCR cache ttl_seconds must be positive.")
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[K, _CacheEntry[V]] = OrderedDict()
        self._estimated_bytes = 0

    @property
    def entry_count(self) -> int:
        self._remove_expired()
        return len(self._entries)

    @property
    def estimated_bytes(self) -> int:
        self._remove_expired()
        return self._estimated_bytes

    def get(self, key: K) -> V | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._clock():
            self._remove(key)
            return None
        self._entries.move_to_end(key)
        return entry.value

    def put(self, key: K, value: V, *, estimated_bytes: int) -> None:
        normalized_size = max(int(estimated_bytes), 1)
        if key in self._entries:
            self._remove(key)
        if normalized_size > self._max_bytes:
            return
        self._entries[key] = _CacheEntry(
            value=value,
            estimated_bytes=normalized_size,
            expires_at=self._clock() + self._ttl_seconds,
        )
        self._estimated_bytes += normalized_size
        self._entries.move_to_end(key)
        self._remove_expired()
        while (
            len(self._entries) > self._max_entries
            or self._estimated_bytes > self._max_bytes
        ):
            oldest_key = next(iter(self._entries))
            self._remove(oldest_key)

    def clear(self) -> None:
        self._entries.clear()
        self._estimated_bytes = 0

    def _remove_expired(self) -> None:
        now = self._clock()
        for key, entry in tuple(self._entries.items()):
            if entry.expires_at <= now:
                self._remove(key)

    def _remove(self, key: K) -> None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._estimated_bytes -= entry.estimated_bytes


class PageOcrSession:
    """Case-local OCR state for viewport recognition and bounded page scans."""

    def __init__(
        self,
        *,
        page: OcrPageLike,
        analyzer: OcrAnalyzer,
        screenshot_provider: ScreenshotProvider | None = None,
        preprocessing_profile: OcrPreprocessingProfile = "balanced",
        max_page_tiles: int = 20,
        page_tile_overlap_ratio: float = 0.20,
        total_timeout_seconds: float = _DEFAULT_TOTAL_TIMEOUT_SECONDS,
        stability_wait_ms: float = 100.0,
        cache_ttl_seconds: float = _DEFAULT_CACHE_TTL_SECONDS,
        cache_max_entries: int = _DEFAULT_CACHE_MAX_ENTRIES,
        cache_memory_limit_bytes: int = _DEFAULT_CACHE_MEMORY_BYTES,
        evidence_max_candidates: int = DEFAULT_MAX_CANDIDATE_SUMMARIES,
        evidence_max_text_length: int = DEFAULT_MAX_TEXT_LENGTH,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_page_tiles < 1:
            raise ValueError("OCR max_page_tiles must be positive.")
        if not 0.0 < page_tile_overlap_ratio <= 0.5:
            raise ValueError(
                "OCR page_tile_overlap_ratio must be greater than zero and at most 0.5."
            )
        if total_timeout_seconds <= 0:
            raise ValueError("OCR total_timeout_seconds must be positive.")
        if stability_wait_ms < 0:
            raise ValueError("OCR stability_wait_ms must not be negative.")
        if cache_memory_limit_bytes < 2:
            raise ValueError("OCR cache memory limit must be at least two bytes.")
        if not 1 <= evidence_max_candidates <= HARD_MAX_CANDIDATE_SUMMARIES:
            raise ValueError(
                "OCR evidence_max_candidates must be between 1 and "
                f"{HARD_MAX_CANDIDATE_SUMMARIES}."
            )
        if not 1 <= evidence_max_text_length <= HARD_MAX_TEXT_LENGTH:
            raise ValueError(
                "OCR evidence_max_text_length must be between 1 and "
                f"{HARD_MAX_TEXT_LENGTH}."
            )

        per_level_bytes = max(cache_memory_limit_bytes // 2, 1)
        self._page = page
        self._analyzer = analyzer
        self._screenshot_provider = (
            screenshot_provider or PlaywrightViewportScreenshotProvider()
        )
        self._preprocessing_profile = preprocessing_profile
        self._max_page_tiles = max_page_tiles
        self._overlap_ratio = page_tile_overlap_ratio
        self._total_timeout_seconds = total_timeout_seconds
        self._stability_wait_ms = stability_wait_ms
        self._evidence_max_candidates = evidence_max_candidates
        self._evidence_max_text_length = evidence_max_text_length
        self._clock = clock
        self._analysis_cache: _TtlLruCache[
            _AnalysisCacheKey, Mapping[str, object]
        ] = _TtlLruCache(
            max_entries=cache_max_entries,
            max_bytes=per_level_bytes,
            ttl_seconds=cache_ttl_seconds,
            clock=clock,
        )
        self._snapshot_cache: _TtlLruCache[
            _SnapshotCacheKey, OcrPageSnapshot
        ] = _TtlLruCache(
            max_entries=cache_max_entries,
            max_bytes=per_level_bytes,
            ttl_seconds=cache_ttl_seconds,
            clock=clock,
        )
        self._navigation_epoch = 0
        self._generation = 0
        self._last_url: str | None = None
        self._last_viewport: tuple[int, int] | None = None
        self._last_scroll: tuple[float, float] | None = None
        self._last_invalidation_reason: str | None = None
        self._analysis_hits = 0
        self._analysis_misses = 0
        self._snapshot_hits = 0
        self._snapshot_misses = 0
        self._scroll_restore_failed = False
        self._active_evidence_captures: list[OcrEvidenceCapture] | None = None
        self._last_evidence: OcrResolutionEvidence | None = None
        self._last_action_evidence: OcrResolutionEvidence | None = None
        self._resolution_evidence: OrderedDict[int, OcrResolutionEvidence] = (
            OrderedDict()
        )

    @property
    def cache_stats(self) -> OcrSessionCacheStats:
        return OcrSessionCacheStats(
            analysis_hits=self._analysis_hits,
            analysis_misses=self._analysis_misses,
            snapshot_hits=self._snapshot_hits,
            snapshot_misses=self._snapshot_misses,
            analysis_entries=self._analysis_cache.entry_count,
            snapshot_entries=self._snapshot_cache.entry_count,
            estimated_bytes=(
                self._analysis_cache.estimated_bytes
                + self._snapshot_cache.estimated_bytes
            ),
            generation=self._generation,
            navigation_epoch=self._navigation_epoch,
            last_invalidation_reason=self._last_invalidation_reason,
        )

    @property
    def last_evidence(self) -> OcrResolutionEvidence | None:
        return self._last_evidence

    @property
    def last_action_evidence(self) -> OcrResolutionEvidence | None:
        return self._last_action_evidence

    def evidence_for(
        self,
        resolution: OcrTargetResolution | None,
    ) -> OcrResolutionEvidence | None:
        if resolution is None:
            return self._last_evidence
        return self._resolution_evidence.get(id(resolution))

    def invalidate(self, reason: str) -> None:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("OCR cache invalidation reason must be non-empty.")
        self._invalidate(
            normalized_reason,
            navigation=normalized_reason in {"navigation", "navigate", "url_changed"},
        )

    def recognize_viewport(
        self,
        *,
        language_profile: OcrLanguageProfile,
    ) -> OcrPageSnapshot:
        geometry = self._read_page_geometry()
        return self._recognize_geometry(
            geometry,
            language_profile=language_profile,
            internal_scroll=False,
        )

    def resolve(self, target: OcrTargetSpec) -> OcrTargetResolution:
        return self._resolve_with_evidence(
            target,
            for_action=False,
            resolver=lambda: self._resolve_target(target),
        )

    def _resolve_target(self, target: OcrTargetSpec) -> OcrTargetResolution:
        if target.scope == "viewport":
            snapshot = self.recognize_viewport(language_profile=target.language)
            return resolve_ocr_target(snapshot, target)
        return self._resolve_page(target)

    def resolve_for_action(self, target: OcrTargetSpec) -> OcrTargetResolution:
        """Resolve twice and return only the freshly revalidated action target."""
        return self._resolve_with_evidence(
            target,
            for_action=True,
            resolver=lambda: self._resolve_for_action_target(target),
        )

    def _resolve_for_action_target(
        self,
        target: OcrTargetSpec,
    ) -> OcrTargetResolution:
        if self._scroll_restore_failed:
            self._raise_revalidation_error(
                target,
                "A prior OCR page scan could not restore the initial scroll position.",
            )
        initial_resolution = self._resolve_target(target)
        if initial_resolution.selected_candidate is None:
            self._raise_revalidation_error(
                target,
                "The initial OCR action resolution returned no selected candidate.",
                candidates=initial_resolution.candidates,
                scanned_tile_count=initial_resolution.scanned_tile_count,
            )

        selected = initial_resolution.selected_candidate
        if target.scope == "page":
            selected_rect = selected.element.coordinates.document_css_rect
            geometry = self._read_page_geometry()
            target_scroll_y = max(
                0.0,
                selected_rect.y
                + selected_rect.height / 2.0
                - geometry.viewport_height / 2.0,
            )
            self._scroll_to(geometry.scroll_x, target_scroll_y)
        self._wait_for_stability()

        # A new generation prevents an identical screenshot checksum from reusing
        # the first OCR analysis. No action may consume the initial resolution.
        self._invalidate("action_revalidation", navigation=False)
        try:
            action_snapshot = self._recognize_geometry(
                self._read_page_geometry(),
                language_profile=target.language,
                internal_scroll=True,
            )
            revalidated = resolve_ocr_target(action_snapshot, target)
        except OcrTargetingError as exc:
            self._raise_revalidation_error(
                target,
                f"Action OCR revalidation failed: {exc.resolution.error_message}",
                candidates=exc.candidates,
                scanned_tile_count=initial_resolution.scanned_tile_count,
            )

        revalidated_candidate = revalidated.selected_candidate
        if revalidated_candidate is None or not _same_action_target(
            selected.element,
            revalidated_candidate.element,
            target=target,
        ):
            self._raise_revalidation_error(
                target,
                (
                    "Action OCR revalidation resolved a target whose matched text, "
                    "role, or action region is inconsistent with the initial target."
                ),
                candidates=revalidated.candidates,
                scanned_tile_count=initial_resolution.scanned_tile_count,
            )

        return OcrTargetResolution(
            status="resolved",
            target=target,
            selected_candidate=revalidated_candidate,
            candidates=revalidated.candidates,
            scanned_tile_count=initial_resolution.scanned_tile_count,
            elapsed_ms=initial_resolution.elapsed_ms + revalidated.elapsed_ms,
        )

    def _resolve_with_evidence(
        self,
        target: OcrTargetSpec,
        *,
        for_action: bool,
        resolver: Callable[[], OcrTargetResolution],
    ) -> OcrTargetResolution:
        if self._active_evidence_captures is not None:
            return resolver()

        before = _evidence_cache_snapshot(self.cache_stats)
        self._active_evidence_captures = []
        started_at = time.perf_counter()
        resolution: OcrTargetResolution | None = None
        error_code: OcrErrorCode | None = None
        try:
            resolution = resolver()
            return resolution
        except OcrTargetingError as exc:
            resolution = exc.resolution
            error_code = exc.code
            raise
        except OcrEngineError as exc:
            error_code = exc.code
            raise
        finally:
            captures = tuple(self._active_evidence_captures)
            self._active_evidence_captures = None
            after = _evidence_cache_snapshot(self.cache_stats)
            revalidation_required = for_action
            revalidation_attempted = (
                revalidation_required
                and (
                    error_code == OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED
                    or (
                        resolution is not None
                        and resolution.status == "resolved"
                    )
                )
            )
            revalidation_passed: bool | None = None
            if revalidation_attempted:
                revalidation_passed = (
                    error_code is None
                    and resolution is not None
                    and resolution.status == "resolved"
                )
            evidence = OcrResolutionEvidence(
                target=target,
                resolution=resolution,
                captures=captures,
                cache_before=before,
                cache_after=after,
                revalidation_required=revalidation_required,
                revalidation_attempted=revalidation_attempted,
                revalidation_passed=revalidation_passed,
                locate_duration_ms=max(
                    0.0,
                    (time.perf_counter() - started_at) * 1000.0,
                ),
                error_code=error_code,
                max_candidate_summaries=self._evidence_max_candidates,
                max_text_length=self._evidence_max_text_length,
            )
            self._last_evidence = evidence
            if for_action:
                self._last_action_evidence = evidence
            if resolution is not None:
                self._resolution_evidence[id(resolution)] = evidence
                self._resolution_evidence.move_to_end(id(resolution))
                while len(self._resolution_evidence) > 16:
                    self._resolution_evidence.popitem(last=False)

    def _resolve_page(self, target: OcrTargetSpec) -> OcrTargetResolution:
        started_at = self._clock()
        initial_geometry = self._read_page_geometry()
        snapshots: list[OcrPageSnapshot] = []
        scanned_bottom = 0.0
        next_scroll_y = 0.0
        resolution: OcrTargetResolution | None = None
        pending_error: OcrTargetingError | None = None

        try:
            while True:
                self._check_scan_timeout(
                    target,
                    started_at=started_at,
                    snapshots=snapshots,
                    scanned_bottom=scanned_bottom,
                )
                self._scroll_to(initial_geometry.scroll_x, next_scroll_y)
                self._wait_for_stability()
                tile_geometry = self._read_page_geometry()
                snapshot = self._recognize_geometry(
                    tile_geometry,
                    language_profile=target.language,
                    internal_scroll=True,
                )
                snapshots.append(snapshot)
                scanned_bottom = max(
                    scanned_bottom,
                    tile_geometry.scroll_y + tile_geometry.viewport_height,
                )
                self._check_scan_timeout(
                    target,
                    started_at=started_at,
                    snapshots=snapshots,
                    scanned_bottom=scanned_bottom,
                )
                merged_snapshot = merge_ocr_page_snapshots(
                    snapshots,
                    initial_scroll_x=initial_geometry.scroll_x,
                    initial_scroll_y=initial_geometry.scroll_y,
                )
                try:
                    resolution = resolve_ocr_target(
                        merged_snapshot,
                        target,
                        scanned_tile_count=len(snapshots),
                    )
                    pending_error = None
                except OcrTargetingError as exc:
                    resolution = None
                    pending_error = exc

                updated_geometry = self._read_page_geometry()
                at_bottom = (
                    updated_geometry.scroll_y + updated_geometry.viewport_height
                    >= updated_geometry.scroll_height - 1.0
                )
                if resolution is not None and _is_unique_high_confidence(resolution):
                    return resolution
                if at_bottom:
                    if resolution is not None:
                        return resolution
                    if pending_error is not None:
                        raise pending_error
                    raise AssertionError("OCR page scan ended without a resolution.")
                if len(snapshots) >= self._max_page_tiles:
                    self._raise_scan_limit(
                        target,
                        snapshots=snapshots,
                        scanned_bottom=scanned_bottom,
                        reason=(
                            f"maximum tile count {self._max_page_tiles} was reached"
                        ),
                        candidates=(
                            pending_error.candidates
                            if pending_error is not None
                            else ()
                        ),
                    )

                step = updated_geometry.viewport_height * (1.0 - self._overlap_ratio)
                maximum_scroll_y = max(
                    0.0,
                    updated_geometry.scroll_height
                    - updated_geometry.viewport_height,
                )
                candidate_scroll_y = min(
                    updated_geometry.scroll_y + max(step, 1.0),
                    maximum_scroll_y,
                )
                if candidate_scroll_y <= updated_geometry.scroll_y + 0.5:
                    self._raise_scan_limit(
                        target,
                        snapshots=snapshots,
                        scanned_bottom=scanned_bottom,
                        reason="the document could not advance to the next scan tile",
                        candidates=(
                            pending_error.candidates
                            if pending_error is not None
                            else ()
                        ),
                    )
                next_scroll_y = candidate_scroll_y
        finally:
            self._restore_initial_scroll(target, initial_geometry)

    def _recognize_geometry(
        self,
        geometry: PageScrollGeometry,
        *,
        language_profile: OcrLanguageProfile,
        internal_scroll: bool,
    ) -> OcrPageSnapshot:
        self._sync_page_state(geometry, internal_scroll=internal_scroll)
        try:
            screenshot_bytes = self._screenshot_provider.capture(self._page)
        except OcrEngineError:
            raise
        except Exception as exc:
            raise OcrEngineError(
                OcrErrorCode.OCR_ANALYSIS_FAILED,
                f"Failed to capture OCR viewport screenshot: {exc}",
            ) from exc
        if not isinstance(screenshot_bytes, bytes) or not screenshot_bytes:
            raise OcrEngineError(
                OcrErrorCode.OCR_ANALYSIS_FAILED,
                "OCR screenshot provider returned no PNG bytes.",
            )

        image_width, image_height = _png_dimensions(screenshot_bytes)
        scale_x = image_width / geometry.viewport_width
        scale_y = image_height / geometry.viewport_height
        if not math.isclose(scale_x, scale_y, rel_tol=0.01, abs_tol=0.01):
            raise OcrPageGeometryError(
                "OCR screenshot has inconsistent horizontal and vertical CSS scale."
            )
        effective_scale = (scale_x + scale_y) / 2.0
        checksum = hashlib.sha256(screenshot_bytes).hexdigest()
        url = str(self._page.url)
        snapshot_key = _SnapshotCacheKey(
            navigation_epoch=self._navigation_epoch,
            generation=self._generation,
            url=url,
            viewport_width=geometry.viewport_width,
            viewport_height=geometry.viewport_height,
            scroll_x=_coordinate_key(geometry.scroll_x),
            scroll_y=_coordinate_key(geometry.scroll_y),
            screenshot_checksum_sha256=checksum,
            language_profile=language_profile,
            preprocessing_profile=self._preprocessing_profile,
        )
        cached_snapshot = self._snapshot_cache.get(snapshot_key)
        if cached_snapshot is not None:
            self._snapshot_hits += 1
            self._record_evidence_capture(
                image_png_bytes=screenshot_bytes,
                snapshot=cached_snapshot,
                snapshot_cache_hit=True,
                analysis_cache_hit=None,
            )
            return cached_snapshot
        self._snapshot_misses += 1

        analysis_key = _AnalysisCacheKey(
            navigation_epoch=self._navigation_epoch,
            generation=self._generation,
            url=url,
            viewport_width=geometry.viewport_width,
            viewport_height=geometry.viewport_height,
            screenshot_checksum_sha256=checksum,
            language_profile=language_profile,
            preprocessing_profile=self._preprocessing_profile,
        )
        analysis = self._analysis_cache.get(analysis_key)
        analysis_cache_hit = analysis is not None
        if analysis is None:
            self._analysis_misses += 1
            try:
                analysis = self._analyzer.analyze_ocr(
                    image_png_bytes=screenshot_bytes,
                    language_profile=language_profile,
                )
            except OcrEngineError:
                raise
            except Exception as exc:
                raise OcrEngineError(
                    OcrErrorCode.OCR_ANALYSIS_FAILED,
                    f"OCR analyzer failed: {exc}",
                ) from exc
            if not isinstance(analysis, Mapping):
                raise OcrEngineError(
                    OcrErrorCode.OCR_ANALYSIS_FAILED,
                    "OCR analyzer returned an invalid analysis object.",
                )
            analysis = dict(analysis)
            self._analysis_cache.put(
                analysis_key,
                analysis,
                estimated_bytes=_estimate_mapping_bytes(analysis),
            )
        else:
            self._analysis_hits += 1

        snapshot = build_ocr_page_snapshot_from_analysis(
            image_png_bytes=screenshot_bytes,
            analysis=analysis,
            viewport_width_css=geometry.viewport_width,
            viewport_height_css=geometry.viewport_height,
            device_scale_factor=effective_scale,
            scroll_x_css=geometry.scroll_x,
            scroll_y_css=geometry.scroll_y,
        )
        self._snapshot_cache.put(
            snapshot_key,
            snapshot,
            estimated_bytes=len(snapshot.model_dump_json().encode("utf-8")),
        )
        self._record_evidence_capture(
            image_png_bytes=screenshot_bytes,
            snapshot=snapshot,
            snapshot_cache_hit=False,
            analysis_cache_hit=analysis_cache_hit,
        )
        return snapshot

    def _record_evidence_capture(
        self,
        *,
        image_png_bytes: bytes,
        snapshot: OcrPageSnapshot,
        snapshot_cache_hit: bool,
        analysis_cache_hit: bool | None,
    ) -> None:
        if self._active_evidence_captures is None:
            return
        self._active_evidence_captures.append(
            OcrEvidenceCapture(
                image_png_bytes=image_png_bytes,
                snapshot=snapshot,
                snapshot_cache_hit=snapshot_cache_hit,
                analysis_cache_hit=analysis_cache_hit,
            )
        )

    def _read_page_geometry(self) -> PageScrollGeometry:
        try:
            raw_geometry = self._page.evaluate(_READ_PAGE_GEOMETRY_SCRIPT)
        except Exception as exc:
            raise OcrEngineError(
                OcrErrorCode.OCR_ANALYSIS_FAILED,
                f"Failed to read document scroll geometry: {exc}",
            ) from exc
        if not isinstance(raw_geometry, Mapping):
            raise OcrEngineError(
                OcrErrorCode.OCR_ANALYSIS_FAILED,
                "Document scroll geometry must be an object.",
            )
        return PageScrollGeometry(
            scroll_x=_finite_number(raw_geometry.get("scroll_x"), "scroll_x"),
            scroll_y=_finite_number(raw_geometry.get("scroll_y"), "scroll_y"),
            scroll_width=_positive_number(
                raw_geometry.get("scroll_width"), "scroll_width"
            ),
            scroll_height=_positive_number(
                raw_geometry.get("scroll_height"), "scroll_height"
            ),
            viewport_width=_positive_integer(
                raw_geometry.get("viewport_width"), "viewport_width"
            ),
            viewport_height=_positive_integer(
                raw_geometry.get("viewport_height"), "viewport_height"
            ),
        )

    def _scroll_to(self, scroll_x: float, scroll_y: float) -> None:
        try:
            self._page.evaluate(
                _SCROLL_PAGE_SCRIPT,
                {"x": max(scroll_x, 0.0), "y": max(scroll_y, 0.0)},
            )
        except Exception as exc:
            raise OcrEngineError(
                OcrErrorCode.OCR_ANALYSIS_FAILED,
                f"Failed to scroll document for OCR scanning: {exc}",
            ) from exc

    def _wait_for_stability(self) -> None:
        if self._stability_wait_ms <= 0:
            return
        self._page.wait_for_timeout(self._stability_wait_ms)

    def _sync_page_state(
        self,
        geometry: PageScrollGeometry,
        *,
        internal_scroll: bool,
    ) -> None:
        url = str(self._page.url)
        viewport = (geometry.viewport_width, geometry.viewport_height)
        scroll = (
            _coordinate_key(geometry.scroll_x),
            _coordinate_key(geometry.scroll_y),
        )
        if self._last_url is not None and url != self._last_url:
            self._invalidate("url_changed", navigation=True)
        elif self._last_viewport is not None and viewport != self._last_viewport:
            self._invalidate("viewport_changed", navigation=False)
        elif (
            not internal_scroll
            and self._last_scroll is not None
            and scroll != self._last_scroll
        ):
            self._invalidate("external_scroll", navigation=False)
        self._last_url = url
        self._last_viewport = viewport
        self._last_scroll = scroll

    def _invalidate(self, reason: str, *, navigation: bool) -> None:
        self._generation += 1
        if navigation:
            self._navigation_epoch += 1
        self._analysis_cache.clear()
        self._snapshot_cache.clear()
        self._last_invalidation_reason = reason

    def _restore_initial_scroll(
        self,
        target: OcrTargetSpec,
        initial: PageScrollGeometry,
    ) -> None:
        try:
            self._scroll_to(initial.scroll_x, initial.scroll_y)
            self._wait_for_stability()
            restored = self._read_page_geometry()
        except Exception as exc:
            self._scroll_restore_failed = True
            self._raise_revalidation_error(
                target,
                f"Failed to restore initial page scroll after OCR scan: {exc}",
            )
        if not (
            math.isclose(restored.scroll_x, initial.scroll_x, abs_tol=1.0)
            and math.isclose(restored.scroll_y, initial.scroll_y, abs_tol=1.0)
        ):
            self._scroll_restore_failed = True
            self._raise_revalidation_error(
                target,
                (
                    "OCR page scan could not restore the initial scroll position; "
                    f"expected ({initial.scroll_x:.2f}, {initial.scroll_y:.2f}), "
                    f"got ({restored.scroll_x:.2f}, {restored.scroll_y:.2f})."
                ),
            )
        self._last_scroll = (
            _coordinate_key(restored.scroll_x),
            _coordinate_key(restored.scroll_y),
        )

    def _check_scan_timeout(
        self,
        target: OcrTargetSpec,
        *,
        started_at: float,
        snapshots: list[OcrPageSnapshot],
        scanned_bottom: float,
    ) -> None:
        if self._clock() - started_at <= self._total_timeout_seconds:
            return
        self._raise_scan_limit(
            target,
            snapshots=snapshots,
            scanned_bottom=scanned_bottom,
            reason=(
                f"total timeout {self._total_timeout_seconds:.3f}s was exceeded"
            ),
        )

    def _raise_scan_limit(
        self,
        target: OcrTargetSpec,
        *,
        snapshots: list[OcrPageSnapshot],
        scanned_bottom: float,
        reason: str,
        candidates: tuple[OcrTargetCandidate, ...] = (),
    ) -> None:
        raise OcrTargetingError(
            OcrTargetResolution(
                status="rejected",
                target=target,
                candidates=candidates,
                error_code=OcrErrorCode.OCR_PAGE_SCAN_LIMIT,
                error_message=(
                    f"OCR page scan stopped because {reason}; scanned "
                    f"{len(snapshots)} tile(s) through document y="
                    f"{scanned_bottom:.2f}."
                ),
                scanned_tile_count=len(snapshots),
            )
        )

    def _raise_revalidation_error(
        self,
        target: OcrTargetSpec,
        message: str,
        *,
        candidates: tuple[OcrTargetCandidate, ...] = (),
        scanned_tile_count: int = 0,
    ) -> None:
        raise OcrTargetingError(
            OcrTargetResolution(
                status="rejected",
                target=target,
                candidates=candidates,
                error_code=OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED,
                error_message=message,
                scanned_tile_count=scanned_tile_count,
            )
        )


def merge_ocr_page_snapshots(
    snapshots: list[OcrPageSnapshot],
    *,
    initial_scroll_x: float,
    initial_scroll_y: float,
) -> OcrPageSnapshot:
    """Merge overlapping viewport snapshots into document-coordinate OCR data."""
    if not snapshots:
        raise ValueError("At least one OCR page snapshot is required.")

    blocks: list[OcrTextBlock] = []
    lines: list[OcrTextLine] = []
    elements: list[OcrTextElement] = []
    relations: list[OcrElementRelation] = []
    element_origins: dict[str, OcrPageSnapshot] = {}
    relation_keys: set[tuple[str, str, str]] = set()

    for tile_number, snapshot in enumerate(snapshots, start=1):
        prefix = f"tile-{tile_number:04d}-"
        block_ids = {
            block.block_id: f"{prefix}{block.block_id}" for block in snapshot.blocks
        }
        line_ids = {
            line.line_id: f"{prefix}{line.line_id}" for line in snapshot.lines
        }
        local_element_ids = {
            element.element_id: f"{prefix}{element.element_id}"
            for element in snapshot.elements
        }
        blocks.extend(
            block.model_copy(update={"block_id": block_ids[block.block_id]})
            for block in snapshot.blocks
        )
        lines.extend(
            line.model_copy(
                update={
                    "line_id": line_ids[line.line_id],
                    "block_ids": tuple(
                        block_ids[block_id] for block_id in line.block_ids
                    ),
                }
            )
            for line in snapshot.lines
        )

        canonical_ids: dict[str, str] = {}
        for element in snapshot.elements:
            duplicate = next(
                (
                    existing
                    for existing in elements
                    if _elements_overlap(
                        existing,
                        element,
                        first_snapshot=element_origins[existing.element_id],
                        second_snapshot=snapshot,
                    )
                ),
                None,
            )
            if duplicate is not None:
                canonical_ids[element.element_id] = duplicate.element_id
                continue
            merged_id = local_element_ids[element.element_id]
            merged_element = element.model_copy(
                update={
                    "element_id": merged_id,
                    "line_ids": tuple(
                        line_ids[line_id] for line_id in element.line_ids
                    ),
                }
            )
            elements.append(merged_element)
            element_origins[merged_id] = snapshot
            canonical_ids[element.element_id] = merged_id

        for relation in snapshot.relations:
            source_id = canonical_ids.get(relation.source_element_id)
            target_id = canonical_ids.get(relation.target_element_id)
            if source_id is None or target_id is None or source_id == target_id:
                continue
            relation_key = (source_id, target_id, relation.type)
            if relation_key in relation_keys:
                continue
            relation_keys.add(relation_key)
            relations.append(
                relation.model_copy(
                    update={
                        "source_element_id": source_id,
                        "target_element_id": target_id,
                    }
                )
            )

    first = snapshots[0]
    checksum = hashlib.sha256(
        "".join(
            snapshot.screenshot_checksum_sha256 for snapshot in snapshots
        ).encode("ascii")
    ).hexdigest()
    return OcrPageSnapshot(
        image_width_px=first.image_width_px,
        image_height_px=first.image_height_px,
        viewport_width_css=first.viewport_width_css,
        viewport_height_css=first.viewport_height_css,
        device_scale_factor=first.device_scale_factor,
        scroll_x_css=initial_scroll_x,
        scroll_y_css=initial_scroll_y,
        language_profiles=tuple(
            dict.fromkeys(
                profile
                for snapshot in snapshots
                for profile in snapshot.language_profiles
            )
        ),
        preprocessing_variants=tuple(
            dict.fromkeys(
                variant
                for snapshot in snapshots
                for variant in snapshot.preprocessing_variants
            )
        ),
        screenshot_checksum_sha256=checksum,
        elapsed_ms=sum(snapshot.elapsed_ms for snapshot in snapshots),
        blocks=tuple(blocks),
        lines=tuple(lines),
        elements=tuple(elements),
        relations=tuple(relations),
    )


def _elements_overlap(
    first: OcrTextElement,
    second: OcrTextElement,
    *,
    first_snapshot: OcrPageSnapshot,
    second_snapshot: OcrPageSnapshot,
) -> bool:
    if normalize_ocr_text(first.text, case_sensitive=False) != normalize_ocr_text(
        second.text,
        case_sensitive=False,
    ):
        return False
    first_document = first.coordinates.document_css_rect
    second_document = second.coordinates.document_css_rect
    if _rect_iou(first_document, second_document) >= 0.45:
        return True
    if _normalized_center_distance(first_document, second_document) <= 0.20:
        return True

    scroll_delta = abs(
        first_snapshot.scroll_y_css - second_snapshot.scroll_y_css
    )
    return (
        scroll_delta > 1.0
        and _rect_iou(
            first.coordinates.viewport_css_rect,
            second.coordinates.viewport_css_rect,
        )
        >= 0.80
    )


def _same_action_target(
    first: OcrTextElement,
    second: OcrTextElement,
    *,
    target: OcrTargetSpec,
) -> bool:
    if normalize_ocr_text(
        first.text,
        case_sensitive=target.case_sensitive,
    ) != normalize_ocr_text(
        second.text,
        case_sensitive=target.case_sensitive,
    ):
        return False
    if first.role != second.role:
        return False

    first_rect = _action_consistency_rect(first, target=target)
    second_rect = _action_consistency_rect(second, target=target)
    if first_rect is None or second_rect is None:
        return False
    return _rect_iou(first_rect, second_rect) >= 0.35 or (
        _normalized_center_distance(first_rect, second_rect) <= 0.25
    )


def _action_consistency_rect(
    element: OcrTextElement,
    *,
    target: OcrTargetSpec,
) -> OcrRect | None:
    if target.action_point == "text_center":
        return (
            element.coordinates.document_css_rect
            if target.scope == "page"
            else element.coordinates.viewport_css_rect
        )

    control_rect = element.associated_control_rect
    if control_rect is None or element.association_ambiguous:
        return None
    if target.scope == "viewport":
        return control_rect

    viewport_rect = element.coordinates.viewport_css_rect
    document_rect = element.coordinates.document_css_rect
    return control_rect.model_copy(
        update={
            "x": control_rect.x + document_rect.x - viewport_rect.x,
            "y": control_rect.y + document_rect.y - viewport_rect.y,
        }
    )


def _is_unique_high_confidence(resolution: OcrTargetResolution) -> bool:
    selected = resolution.selected_candidate
    if selected is None or selected.total_score < 0.95:
        return False
    if resolution.target.ambiguity_margin > 0:
        return False
    if resolution.target.occurrence > 1:
        return False
    return len(resolution.candidates) == 1


def _png_dimensions(image_png_bytes: bytes) -> tuple[int, int]:
    if (
        len(image_png_bytes) < 24
        or image_png_bytes[:8] != _PNG_SIGNATURE
        or image_png_bytes[12:16] != b"IHDR"
    ):
        raise OcrPageGeometryError("OCR screenshot is not a valid PNG image.")
    width, height = struct.unpack(">II", image_png_bytes[16:24])
    if width <= 0 or height <= 0:
        raise OcrPageGeometryError("OCR screenshot dimensions must be positive.")
    return width, height


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OcrEngineError(
            OcrErrorCode.OCR_ANALYSIS_FAILED,
            f"Document geometry field `{field}` must be numeric.",
        )
    result = float(value)
    if not math.isfinite(result):
        raise OcrEngineError(
            OcrErrorCode.OCR_ANALYSIS_FAILED,
            f"Document geometry field `{field}` must be finite.",
        )
    return result


def _positive_number(value: object, field: str) -> float:
    result = _finite_number(value, field)
    if result <= 0:
        raise OcrEngineError(
            OcrErrorCode.OCR_ANALYSIS_FAILED,
            f"Document geometry field `{field}` must be positive.",
        )
    return result


def _positive_integer(value: object, field: str) -> int:
    result = _positive_number(value, field)
    rounded = int(round(result))
    if not math.isclose(result, rounded, abs_tol=0.01):
        raise OcrEngineError(
            OcrErrorCode.OCR_ANALYSIS_FAILED,
            f"Document geometry field `{field}` must be an integer.",
        )
    return rounded


def _coordinate_key(value: float) -> float:
    return round(float(value), 3)


def _estimate_mapping_bytes(value: Mapping[str, object]) -> int:
    try:
        return len(
            json.dumps(
                value,
                ensure_ascii=True,
                separators=(",", ":"),
                default=repr,
            ).encode("utf-8")
        )
    except (TypeError, ValueError):
        return len(repr(value).encode("utf-8"))


def _evidence_cache_snapshot(
    stats: OcrSessionCacheStats,
) -> OcrEvidenceCacheSnapshot:
    return OcrEvidenceCacheSnapshot(
        analysis_hits=stats.analysis_hits,
        analysis_misses=stats.analysis_misses,
        snapshot_hits=stats.snapshot_hits,
        snapshot_misses=stats.snapshot_misses,
        generation=stats.generation,
        last_invalidation_reason=stats.last_invalidation_reason,
    )


def _rect_iou(first: OcrRect, second: OcrRect) -> float:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = (
        first.width * first.height
        + second.width * second.height
        - intersection
    )
    return intersection / union if union > 0 else 0.0


def _normalized_center_distance(first: OcrRect, second: OcrRect) -> float:
    first_center = (
        first.x + first.width / 2.0,
        first.y + first.height / 2.0,
    )
    second_center = (
        second.x + second.width / 2.0,
        second.y + second.height / 2.0,
    )
    scale = max(
        first.width,
        first.height,
        second.width,
        second.height,
        1.0,
    )
    return math.dist(first_center, second_center) / scale
