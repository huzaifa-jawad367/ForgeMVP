with open("tests/test_mvp_acceptance_protocol.py", "r") as f:
    code = f.read()

# Make sure EdgePayload in tests also sets boot_id to `edge.boot_id`
code = code.replace(
"""            payload = EdgePayload(
                payload_id=f"nom_{i}",""",
"""            payload = EdgePayload(
                payload_id=f"nom_{i}",
                boot_id=edge.boot_id,""")

code = code.replace(
"""            payload = EdgePayload(
                payload_id=f"anom_{i}",""",
"""            payload = EdgePayload(
                payload_id=f"anom_{i}",
                boot_id=edge.boot_id,""")

code = code.replace(
"""            payload = EdgePayload(
                payload_id=f"off_{i}",""",
"""            payload = EdgePayload(
                payload_id=f"off_{i}",
                boot_id=edge.boot_id,""")

# We also need to "Add a test that the same sequence numbers under a new boot_id are inserted, not deduplicated."
# This can be done by pushing a new frame via backend API with a new boot_id but same sequence number.

test_addition = """
        # Test that the same sequence numbers under a NEW boot_id are inserted, not deduplicated
        new_boot_id = "test-boot-id-new-12345"
        dup_frames_data_new_boot = []
        for f in offline_frames[:3]:
            # copy fields
            f_dict = {
                "payload_id": f.payload_id + "_new",
                "boot_id": new_boot_id, # new boot id
                "frame_index": f.frame_index,
                "sequence_number": f.sequence_number, # SAME sequence number
                "timestamps": f.timestamps,
                "has_anomaly": f.has_anomaly,
                "fps": f.fps,
                "inference_time_ms": f.inference_time_ms,
                "brightness": f.brightness,
                "blur_score": f.blur_score,
                "noise_score": f.noise_score,
                "noise_level": f.noise_level,
                "num_detections": f.num_detections,
                "detections": f.detections,
            }
            dup_frames_data_new_boot.append(f_dict)

        sync_payload_new_boot = {
            "schema_version": SCHEMA_VERSION,
            "boot_id": new_boot_id,
            "sequence_range": {"start": 0, "end": 2},
            "transmitted_at_ms": time.time() * 1000,
            "edge_id": edge2.edge_id,
            "source_id": "visa:pcb1",
            "batch_id": "batch-new-boot-001",
            "frames": dup_frames_data_new_boot,
            "edge_buffer_stats": {
                "queue_size": 0,
                "total_synced": 3,
                "total_dropped": 0,
            },
            "latest_frame_jpeg": None,
        }

        req_new_boot = urllib.request.Request(
            sync_url,
            data=json.dumps(sync_payload_new_boot).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with get_session() as session:
            count_before_new = session.query(FrameMetric).count()

        with urllib.request.urlopen(req_new_boot, timeout=3.0) as resp:
            self.assertEqual(resp.status, 200)

        with get_session() as session:
            count_after_new = session.query(FrameMetric).count()

        # Deduplication must NOT happen for a different boot_id!
        # We pushed 3 frames, so it should insert 3 new records
        self.assertEqual(count_after_new, count_before_new + 3)
"""

code = code.replace(
"""        # Deduplication must result in 0 new inserted records
        self.assertEqual(count_before, count_after)""",
"""        # Deduplication must result in 0 new inserted records
        self.assertEqual(count_before, count_after)""" + test_addition
)

with open("tests/test_mvp_acceptance_protocol.py", "w") as f:
    f.write(code)
