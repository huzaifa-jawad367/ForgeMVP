with open("tests/test_mvp_acceptance_protocol.py", "r") as f:
    code = f.read()

# I forgot to pass `boot_id` into the test for deduplication! Wait.
# I wrote:
#         sync_payload = {
#             "schema_version": SCHEMA_VERSION,
#             "boot_id": edge2.boot_id,

# Wait, `edge2.boot_id` is the NEW boot_id after restart!!!
# The original frames were buffered under `edge.boot_id`!
# When `edge2` restarted, we sent a manual duplicate batch with `edge2.boot_id`.
# BUT they were never sent before with `edge2.boot_id`! They were sent with `edge.boot_id`?
# NO, wait! The frames buffered in `offline_frames` were pushed into `edge` (which has `edge.boot_id`).
# But when `edge2` started and drained the queue, it drained them. What boot_id did they have?
# I modified `EdgePayload` to store `boot_id`.
# So when `edge2` synced them, they were synced with `edge.boot_id`.
# Wait, look at `sync_payload`:
#             "boot_id": edge2.boot_id, # THIS IS WRONG!
# If I use `edge2.boot_id`, it will be a different boot_id! Thus NOT deduplicated!
# The duplicate test SHOULD use the original `boot_id` that the frames had, which is `edge.boot_id`.

code = code.replace(
"""        sync_payload = {
            "schema_version": SCHEMA_VERSION,
            "boot_id": edge2.boot_id,""",
"""        sync_payload = {
            "schema_version": SCHEMA_VERSION,
            "boot_id": edge.boot_id,"""
)

# And wait... I need to make sure the frames themselves have the correct boot_id in the manual batch!
code = code.replace(
"""            dup_frames_data.append({
                "payload_id": f.payload_id,
                "frame_index": f.frame_index,
                "sequence_number": f.sequence_number,
                "timestamps": f.timestamps,""",
"""            dup_frames_data.append({
                "payload_id": f.payload_id,
                "boot_id": edge.boot_id,
                "frame_index": f.frame_index,
                "sequence_number": f.sequence_number,
                "timestamps": f.timestamps,"""
)

with open("tests/test_mvp_acceptance_protocol.py", "w") as f:
    f.write(code)
