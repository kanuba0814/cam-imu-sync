import sqlite3
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import Imu
import numpy as np

path = "/home/gxxl/slam_ws_v2/bags/goalDebug/h30_150hz_slowMove/h30_150hz_slowMove_0.db3"
con = sqlite3.connect(path)
imu_id = con.execute("select id from topics where name = '/sync/imu'").fetchone()[0]
rows = con.execute(
    "select data, timestamp from messages where topic_id = ? order by timestamp",
    (imu_id,),
).fetchall()

ts0 = rows[0][1]
samples = []
for r in rows:
    msg = deserialize_message(r[0], Imu)
    t = (r[1] - ts0) * 1e-9
    samples.append((
        t,
        msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z,
        msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z,
    ))
samples = np.array(samples)
print("total: %d samples spanning %.1fs" % (len(samples), samples[-1, 0]))
print("")


def stats(a, b):
    s = samples[(samples[:, 0] >= a) & (samples[:, 0] < b)]
    if len(s) < 10:
        return None
    g_norm = np.linalg.norm(s[:, 1:4], axis=1)
    a_mean = s[:, 4:7].mean(axis=0)
    return {
        "n": len(s),
        "gn_mean_degs": float(np.degrees(g_norm.mean())),
        "gn_std_degs":  float(np.degrees(g_norm.std())),
        "gx_mean_degs": float(np.degrees(s[:, 1].mean())),
        "gy_mean_degs": float(np.degrees(s[:, 2].mean())),
        "gz_mean_degs": float(np.degrees(s[:, 3].mean())),
        "a_norm":       float(np.linalg.norm(a_mean)),
        "a_xyz":        [float(v) for v in a_mean],
    }


print("=== rotational activity in 1s windows, every 5s ===")
print("t_start  gnorm_mean_degs  gn_std_degs  gx_mean  gy_mean  gz_mean  acc_norm")
for t in range(0, int(samples[-1, 0]), 5):
    s = stats(t, t + 1)
    if s is None:
        continue
    print("%6d  %14.2f  %10.2f  %+7.2f  %+7.2f  %+7.2f  %7.3f" % (
        t, s["gn_mean_degs"], s["gn_std_degs"],
        s["gx_mean_degs"], s["gy_mean_degs"], s["gz_mean_degs"], s["a_norm"],
    ))

print("")
print("=== quietest 2s window (lowest |gyro| std) ===")
quiet = None
t = 0.0
end = samples[-1, 0] - 2.0
while t < end:
    s = stats(t, t + 2)
    if s is not None:
        if quiet is None or s["gn_std_degs"] < quiet[1]["gn_std_degs"]:
            quiet = (t, s)
    t += 0.5
print("window t=%.1f s" % quiet[0])
print("  gyro mean (deg/s): x=%+.3f y=%+.3f z=%+.3f" % (
    quiet[1]["gx_mean_degs"], quiet[1]["gy_mean_degs"], quiet[1]["gz_mean_degs"],
))
print("  gyro mean (rad/s): x=%+.5f y=%+.5f z=%+.5f" % (
    np.radians(quiet[1]["gx_mean_degs"]),
    np.radians(quiet[1]["gy_mean_degs"]),
    np.radians(quiet[1]["gz_mean_degs"]),
))
print("  accel mean (m/s²): x=%+.4f y=%+.4f z=%+.4f |a|=%.4f" % (
    quiet[1]["a_xyz"][0], quiet[1]["a_xyz"][1], quiet[1]["a_xyz"][2],
    quiet[1]["a_norm"],
))
print("  total |gyro|: mean=%.3f deg/s std=%.3f" % (
    quiet[1]["gn_mean_degs"], quiet[1]["gn_std_degs"],
))
