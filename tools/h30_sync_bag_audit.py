#!/usr/bin/env python3
"""Audit H30 sync-only rosbag2 inputs for ORB-SLAM3 diagnosis.

The audit is intentionally offline: it opens rosbag2 data only and never
starts camera, IMU, cam_imu_sync, or ORB wrapper nodes.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


TOPICS_TO_CHECK = (
    "/sync/image_raw",
    "/sync/imu",
    "/sync/imu_batch",
    "/imu/pipeline_ready",
    "/rosout",
)
HARD_REQUIRED_TOPICS = ("/sync/image_raw", "/sync/imu")
DESERIALIZE_TOPICS = set(TOPICS_TO_CHECK)
RATE_TARGETS_HZ = {
    "/sync/image_raw": 30.0,
    "/sync/imu": 100.0,
}


@dataclass
class TopicSamples:
    count: int = 0
    storage_stamps: list[float] = field(default_factory=list)
    header_stamps: list[float] = field(default_factory=list)
    header_monotonic: bool = True
    header_violations: int = 0
    nan_count: int = 0
    acc_xyz: list[tuple[float, float, float, float]] = field(default_factory=list)
    gyro_xyz: list[tuple[float, float, float, float]] = field(default_factory=list)
    image_encodings: Counter[str] = field(default_factory=Counter)
    image_sizes: Counter[str] = field(default_factory=Counter)
    bool_values: Counter[str] = field(default_factory=Counter)
    rosout_levels: Counter[str] = field(default_factory=Counter)
    rosout_names: Counter[str] = field(default_factory=Counter)
    rosout_messages: list[str] = field(default_factory=list)


def _resolve_bag_uri(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.name == "metadata.yaml" or path.suffix == ".db3":
        return path.parent
    return path


def _stamp_to_sec(stamp: Any) -> float:
    return float(stamp.sec) + float(stamp.nanosec) * 1e-9


def _header_stamp(msg: Any) -> float | None:
    header = getattr(msg, "header", None)
    stamp = getattr(header, "stamp", None) if header is not None else None
    return _stamp_to_sec(stamp) if stamp is not None else None


def _count_nans(value: Any) -> int:
    if isinstance(value, float):
        return 1 if math.isnan(value) else 0
    if isinstance(value, (str, bytes, bytearray, bool, int)):
        return 0
    if isinstance(value, (list, tuple)):
        return sum(_count_nans(item) for item in value)
    slots = getattr(value, "__slots__", None)
    if not slots:
        return 0
    total = 0
    for slot in slots:
        name = slot[1:] if slot.startswith("_") else slot
        if hasattr(value, name):
            total += _count_nans(getattr(value, name))
    return total


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * pct / 100.0
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(ordered[lo])
    return float(ordered[lo] * (hi - rank) + ordered[hi] * (rank - lo))


def _mean(values: list[float]) -> float | None:
    return float(statistics.mean(values)) if values else None


def _pstdev(values: list[float]) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return 0.0
    return float(statistics.pstdev(values))


def _stats(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "p50": _percentile(values, 50.0),
        "p95": _percentile(values, 95.0),
        "max": max(values) if values else None,
        "mean": _mean(values),
        "std": _pstdev(values),
    }


def _rate(stamps: list[float]) -> float | None:
    if len(stamps) < 2:
        return None
    span = stamps[-1] - stamps[0]
    return (len(stamps) - 1) / span if span > 0.0 else None


def _period_stats(stamps: list[float]) -> dict[str, float | int | None]:
    periods = [
        stamps[index] - stamps[index - 1]
        for index in range(1, len(stamps))
    ]
    result = _stats(periods)
    result["unit"] = "sec"
    return result


def _first_last(values: list[float]) -> dict[str, float | None]:
    return {"first": values[0] if values else None, "last": values[-1] if values else None}


def _norm3(x: float, y: float, z: float) -> float:
    return math.sqrt(x * x + y * y + z * z)


def _vec_mean(samples: list[tuple[float, float, float, float]]) -> list[float] | None:
    if not samples:
        return None
    return [float(statistics.mean(item[index] for item in samples)) for index in (1, 2, 3)]


def _vec_norms(samples: list[tuple[float, float, float, float]]) -> list[float]:
    return [_norm3(item[1], item[2], item[3]) for item in samples]


def _slice_first_seconds(
    samples: list[tuple[float, float, float, float]],
    seconds: float,
) -> list[tuple[float, float, float, float]]:
    if not samples:
        return []
    start = samples[0][0]
    return [item for item in samples if item[0] - start <= seconds]


def _nearest_delta_ms(image_stamps: list[float], imu_stamps: list[float]) -> dict[str, Any]:
    deltas: list[float] = []
    if image_stamps and imu_stamps:
        ordered_imu = sorted(imu_stamps)
        for stamp in image_stamps:
            index = bisect.bisect_left(ordered_imu, stamp)
            candidates = []
            if index > 0:
                candidates.append(ordered_imu[index - 1])
            if index < len(ordered_imu):
                candidates.append(ordered_imu[index])
            nearest = min(candidates, key=lambda imu_stamp: abs(stamp - imu_stamp))
            deltas.append((stamp - nearest) * 1000.0)
    result = _stats(deltas)
    result["unit"] = "ms"
    return result


def _header_minus_storage(
    header_stamps: list[float],
    storage_stamps: list[float],
) -> dict[str, Any]:
    deltas = [
        header - storage
        for header, storage in zip(header_stamps, storage_stamps)
    ]
    result = _stats(deltas)
    result["unit"] = "sec"
    return result


def _deserialize_class(topic_types: dict[str, str]) -> dict[str, Any | None]:
    classes: dict[str, Any | None] = {}
    for topic, type_name in topic_types.items():
        if topic not in DESERIALIZE_TOPICS:
            classes[topic] = None
            continue
        try:
            classes[topic] = get_message(type_name)
        except (AttributeError, ModuleNotFoundError, ValueError):
            classes[topic] = None
    return classes


def _record_imu(samples: TopicSamples, msg: Any, stamp: float | None) -> None:
    if stamp is None:
        return
    acc = getattr(msg, "linear_acceleration", None)
    gyro = getattr(msg, "angular_velocity", None)
    if acc is not None:
        samples.acc_xyz.append((stamp, float(acc.x), float(acc.y), float(acc.z)))
    if gyro is not None:
        samples.gyro_xyz.append((stamp, float(gyro.x), float(gyro.y), float(gyro.z)))


def _record_image(samples: TopicSamples, msg: Any) -> None:
    encoding = getattr(msg, "encoding", "")
    width = getattr(msg, "width", None)
    height = getattr(msg, "height", None)
    step = getattr(msg, "step", None)
    if encoding:
        samples.image_encodings[str(encoding)] += 1
    if width is not None and height is not None:
        samples.image_sizes[f"{width}x{height}@step{step}"] += 1


def _record_aux(samples: TopicSamples, topic: str, msg: Any) -> None:
    if topic == "/imu/pipeline_ready":
        samples.bool_values[str(bool(getattr(msg, "data", False)))] += 1
    if topic == "/rosout":
        samples.rosout_levels[str(getattr(msg, "level", ""))] += 1
        samples.rosout_names[str(getattr(msg, "name", ""))] += 1
        text = str(getattr(msg, "msg", ""))
        if text and len(samples.rosout_messages) < 20:
            samples.rosout_messages.append(text[:500])


def _read_bag_samples(bag_uri: Path) -> tuple[dict[str, str], dict[str, TopicSamples]]:
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_uri), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("", ""),
    )
    topic_types = {topic.name: topic.type for topic in reader.get_all_topics_and_types()}
    message_classes = _deserialize_class(topic_types)
    samples: dict[str, TopicSamples] = defaultdict(TopicSamples)
    for topic in topic_types:
        samples[topic]

    while reader.has_next():
        topic, data, storage_time_ns = reader.read_next()
        item = samples[topic]
        item.count += 1
        item.storage_stamps.append(storage_time_ns * 1e-9)
        msg_type = message_classes.get(topic)
        if msg_type is None:
            continue
        msg = deserialize_message(data, msg_type)
        item.nan_count += _count_nans(msg)
        stamp = _header_stamp(msg)
        if stamp is not None:
            if item.header_stamps and stamp < item.header_stamps[-1]:
                item.header_monotonic = False
                item.header_violations += 1
            item.header_stamps.append(stamp)
        if topic in ("/sync/imu", "/sync/imu_batch"):
            _record_imu(item, msg, stamp)
        elif topic == "/sync/image_raw":
            _record_image(item, msg)
        else:
            _record_aux(item, topic, msg)

    return topic_types, samples


def _imu_unit_hint(acc_norms: list[float], gyro_norms: list[float]) -> str:
    acc_mean = _mean(acc_norms)
    gyro_mean = _mean(gyro_norms)
    hints = []
    if acc_mean is None:
        hints.append("no_acc_samples")
    elif 8.0 <= acc_mean <= 11.5:
        hints.append("acc_mps2_like")
    elif 0.8 <= acc_mean <= 1.2:
        hints.append("acc_g_like_FAIL_for_ORB")
    else:
        hints.append("acc_norm_unexpected")
    if gyro_mean is None:
        hints.append("no_gyro_samples")
    elif gyro_mean < 0.2:
        hints.append("static_gyro_radps_like")
    else:
        hints.append("static_gyro_not_near_zero")
    return ",".join(hints)


def _topic_result(topic: str, type_name: str | None, samples: TopicSamples) -> dict[str, Any]:
    stamps_for_rate = samples.header_stamps or samples.storage_stamps
    return {
        "topic": topic,
        "type": type_name,
        "count": samples.count,
        "present_in_metadata": type_name is not None,
        "has_messages": samples.count > 0,
        "header_stamp": _first_last(samples.header_stamps),
        "bag_receive_time": _first_last(samples.storage_stamps),
        "rate_hz": _rate(stamps_for_rate),
        "period": _period_stats(samples.header_stamps),
        "header_stamp_monotonic": samples.header_monotonic,
        "header_stamp_violations": samples.header_violations,
        "header_minus_receive": _header_minus_storage(samples.header_stamps, samples.storage_stamps),
        "nan_count": samples.nan_count,
        "image_encodings": dict(samples.image_encodings.most_common()),
        "image_sizes": dict(samples.image_sizes.most_common()),
        "bool_values": dict(samples.bool_values.most_common()),
        "rosout_levels": dict(samples.rosout_levels.most_common()),
        "rosout_names": dict(samples.rosout_names.most_common(10)),
        "rosout_sample_messages": samples.rosout_messages,
    }


def _imu_result(samples: TopicSamples, static_seconds: float) -> dict[str, Any]:
    static_acc = _slice_first_seconds(samples.acc_xyz, static_seconds)
    static_gyro = _slice_first_seconds(samples.gyro_xyz, static_seconds)
    acc_norms = _vec_norms(static_acc)
    gyro_norms = _vec_norms(static_gyro)
    return {
        "static_seconds": static_seconds,
        "static_sample_count": len(static_acc),
        "mean_acc_xyz": _vec_mean(static_acc),
        "mean_gyro_xyz": _vec_mean(static_gyro),
        "acc_norm": _stats(acc_norms),
        "gyro_norm": _stats(gyro_norms),
        "whole_bag_gyro_norm": _stats(_vec_norms(samples.gyro_xyz)),
        "unit_hint": _imu_unit_hint(acc_norms, gyro_norms),
    }


def _status_from_checks(
    topic_results: dict[str, dict[str, Any]],
    imu_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    for topic in HARD_REQUIRED_TOPICS:
        result = topic_results[topic]
        if result["count"] <= 0:
            failures.append(f"{topic} absent_or_empty")
    for topic in ("/sync/imu_batch", "/imu/pipeline_ready"):
        result = topic_results[topic]
        if result["present_in_metadata"] and result["count"] == 0:
            warnings.append(f"{topic} present_but_empty")
        elif not result["present_in_metadata"]:
            warnings.append(f"{topic} absent_from_metadata")
    if not topic_results["/rosout"]["present_in_metadata"]:
        warnings.append("/rosout absent_from_metadata")

    for topic in HARD_REQUIRED_TOPICS:
        result = topic_results[topic]
        if not result["header_stamp_monotonic"]:
            failures.append(f"{topic} header_stamp_not_monotonic")
        target_hz = RATE_TARGETS_HZ[topic]
        actual_hz = result.get("rate_hz")
        if actual_hz is None:
            failures.append(f"{topic} rate_unavailable")
        elif actual_hz < target_hz * 0.5 or actual_hz > target_hz * 2.2:
            failures.append(
                f"{topic} rate_abnormal actual={actual_hz:.3f}Hz target~{target_hz:.1f}Hz"
            )

    imu = imu_results.get("/sync/imu")
    if not imu:
        failures.append("/sync/imu unit_check_no_samples")
    else:
        hint = imu.get("unit_hint", "")
        if "acc_g_like_FAIL_for_ORB" in hint:
            failures.append("/sync/imu acceleration_looks_like_g_units")
        if "acc_norm_unexpected" in hint:
            failures.append("/sync/imu static_acc_norm_unexpected")
        if "static_gyro_not_near_zero" in hint:
            failures.append("/sync/imu static_gyro_not_near_zero")

    return {
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "warnings": warnings,
    }


def _alignment_semantics(alignment: dict[str, Any]) -> str:
    p50 = alignment.get("p50")
    p95 = alignment.get("p95")
    if p50 is None or p95 is None:
        return "insufficient_samples"
    if abs(float(p50)) <= 5.0 and abs(float(p95)) <= 8.0:
        return "aligned_time_domain_offset_should_be_0"
    if 10.0 <= abs(float(p50)) <= 20.0:
        return "p50_near_15ms_check_cam_imu_sync_stamp_logic"
    return "ambiguous_alignment"


def audit_one_bag(bag_path: Path, label: str, static_seconds: float) -> dict[str, Any]:
    bag_uri = _resolve_bag_uri(bag_path)
    if not bag_uri.exists():
        raise FileNotFoundError(f"bag path does not exist: {bag_uri}")
    topic_types, samples = _read_bag_samples(bag_uri)
    topic_results = {
        topic: _topic_result(topic, topic_types.get(topic), samples.get(topic, TopicSamples()))
        for topic in TOPICS_TO_CHECK
    }
    imu_results = {
        topic: _imu_result(samples[topic], static_seconds)
        for topic in ("/sync/imu", "/sync/imu_batch")
        if samples.get(topic) and samples[topic].acc_xyz
    }
    alignment = _nearest_delta_ms(
        samples.get("/sync/image_raw", TopicSamples()).header_stamps,
        samples.get("/sync/imu", TopicSamples()).header_stamps,
    )
    return {
        "label": label,
        "bag_path": str(bag_uri),
        "bag_name": bag_uri.name,
        "topic_results": topic_results,
        "imu_results": imu_results,
        "sync_image_minus_nearest_sync_imu": alignment,
        "sync_alignment_semantics": _alignment_semantics(alignment),
        "status": _status_from_checks(topic_results, imu_results),
    }


def _fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _topic_table_lines(bag: dict[str, Any]) -> list[str]:
    lines = [
        "| Topic | Metadata | Count | Type | Header First | Header Last | Rate Hz | Period Mean ms | Period Std ms | Monotonic | NaNs | Extra |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for topic in TOPICS_TO_CHECK:
        result = bag["topic_results"][topic]
        header = result["header_stamp"]
        period = result["period"]
        extra = ""
        if topic == "/sync/image_raw":
            extra = f"{result['image_encodings']} {result['image_sizes']}"
        elif topic == "/imu/pipeline_ready":
            extra = str(result["bool_values"])
        elif topic == "/rosout":
            extra = f"levels={result['rosout_levels']} names={result['rosout_names']}"
        lines.append(
            "| `{topic}` | {metadata} | {count} | `{type_name}` | {first} | {last} | "
            "{rate} | {period_mean} | {period_std} | {mono} | {nan} | {extra} |".format(
                topic=topic,
                metadata=result["present_in_metadata"],
                count=result["count"],
                type_name=result["type"],
                first=_fmt(header["first"], 3),
                last=_fmt(header["last"], 3),
                rate=_fmt(result["rate_hz"], 3),
                period_mean=_fmt(
                    period["mean"] * 1000.0 if period["mean"] is not None else None,
                    3,
                ),
                period_std=_fmt(
                    period["std"] * 1000.0 if period["std"] is not None else None,
                    3,
                ),
                mono=result["header_stamp_monotonic"],
                nan=result["nan_count"],
                extra=extra,
            )
        )
    return lines


def _alignment_lines(bag: dict[str, Any]) -> list[str]:
    result = bag["sync_image_minus_nearest_sync_imu"]
    return [
        "| Metric | Count | Min ms | P50 ms | P95 ms | Max ms | Interpretation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        "| `sync_image_minus_nearest_sync_imu` | {count} | {minv} | {p50} | {p95} | {maxv} | {interp} |".format(
            count=result["count"],
            minv=_fmt(result["min"], 3),
            p50=_fmt(result["p50"], 3),
            p95=_fmt(result["p95"], 3),
            maxv=_fmt(result["max"], 3),
            interp=bag["sync_alignment_semantics"],
        ),
    ]


def _imu_lines(bag: dict[str, Any]) -> list[str]:
    lines = [
        "| Topic | Samples | Mean Acc XYZ | Acc Norm Mean | Acc Norm Std | Acc Norm P95 | Mean Gyro XYZ | Gyro Norm Mean | Gyro Norm Std | Gyro Norm P95 | Unit Hint |",
        "| --- | ---: | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for topic in ("/sync/imu", "/sync/imu_batch"):
        result = bag["imu_results"].get(topic)
        if not result:
            lines.append(f"| `{topic}` | 0 |  |  |  |  |  |  |  |  | no_samples |")
            continue
        acc_norm = result["acc_norm"]
        gyro_norm = result["gyro_norm"]
        lines.append(
            "| `{topic}` | {samples} | {acc_xyz} | {acc_mean} | {acc_std} | {acc_p95} | "
            "{gyro_xyz} | {gyro_mean} | {gyro_std} | {gyro_p95} | {hint} |".format(
                topic=topic,
                samples=result["static_sample_count"],
                acc_xyz=_fmt(result["mean_acc_xyz"]),
                acc_mean=_fmt(acc_norm["mean"]),
                acc_std=_fmt(acc_norm["std"]),
                acc_p95=_fmt(acc_norm["p95"]),
                gyro_xyz=_fmt(result["mean_gyro_xyz"]),
                gyro_mean=_fmt(gyro_norm["mean"]),
                gyro_std=_fmt(gyro_norm["std"]),
                gyro_p95=_fmt(gyro_norm["p95"]),
                hint=result["unit_hint"],
            )
        )
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 01 Sync Bag Audit",
        "",
        f"- output_root: `{report['output_root']}`",
        f"- main_bag: `{report['main']['bag_path']}`",
        f"- static_bag: `{report['static']['bag_path']}`" if report.get("static") else "- static_bag: ``",
        f"- overall_status: **{report['overall_status']}**",
        "- raw_image_requirement: `/image_raw` is intentionally not required or read",
        "",
        "## Hypothesis",
        "",
        "The sync-only bags are valid inputs if `/sync/image_raw` is near 30Hz, `/sync/imu` is near 100Hz, both header stamps are monotonic, and static IMU units look like m/s^2 plus rad/s. If image-to-nearest-IMU p50 is near zero, the ORB wrapper should use `cam_imu_time_offset=0.0` for these sync topics.",
        "",
        "## Evidence",
        "",
    ]
    for label in ("main", "static"):
        bag = report.get(label)
        if not bag:
            continue
        status = bag["status"]
        lines.extend([
            f"### {label.capitalize()} Bag",
            "",
            f"- bag_name: `{bag['bag_name']}`",
            f"- bag_path: `{bag['bag_path']}`",
            f"- status: **{status['status']}**",
            f"- failures: `{status['failures']}`",
            f"- warnings: `{status['warnings']}`",
            "",
            "#### Topic Presence And Timing",
            "",
            *_topic_table_lines(bag),
            "",
            "#### Sync Time-Domain Check",
            "",
            *_alignment_lines(bag),
            "",
            "#### Static IMU Unit Check",
            "",
            *_imu_lines(bag),
            "",
        ])
    lines.extend([
        "## Stage-1 Gate",
        "",
        f"- result: **{report['overall_status']}**",
        "- stop_reason: `none`" if report["overall_status"] == "PASS" else f"- stop_reason: `{report['failures']}`",
        "- next_step: run stage 2 monocular sync-image validation" if report["overall_status"] == "PASS" else "- next_step: stop before ORB and fix the failed data source",
    ])
    return "\n".join(lines) + "\n"


def audit(
    main_bag: Path,
    output_root: Path,
    static_bag: Path | None,
    static_seconds: float,
) -> dict[str, Any]:
    output_root = output_root.expanduser().resolve()
    main_result = audit_one_bag(main_bag, "main", static_seconds)
    static_result = audit_one_bag(static_bag, "static", static_seconds) if static_bag else None
    failures = list(main_result["status"]["failures"])
    if static_result:
        failures.extend(static_result["status"]["failures"])
    report = {
        "output_root": str(output_root),
        "main": main_result,
        "static": static_result,
        "overall_status": "FAIL" if failures else "PASS",
        "failures": failures,
    }
    latest_dir = output_root / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    (latest_dir / "01_sync_bag_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (latest_dir / "01_sync_bag_audit.md").write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-bag", required=True, type=Path)
    parser.add_argument("--static-bag", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path.cwd() / "debug_runs")
    parser.add_argument("--static-seconds", type=float, default=15.0)
    args = parser.parse_args()
    report = audit(args.main_bag, args.output_root, args.static_bag, args.static_seconds)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["overall_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
