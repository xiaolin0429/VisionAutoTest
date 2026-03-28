from __future__ import annotations


def dump_model(schema_cls, obj):
    return schema_cls.model_validate(obj).model_dump(mode="json")


def dump_list(schema_cls, items):
    return [dump_model(schema_cls, item) for item in items]


def dump_plain(obj):
    return {key: value for key, value in vars(obj).items() if not key.startswith("_")}


def dump_plain_list(items):
    return [dump_plain(item) for item in items]
