with open("main.py", "r") as f:
    main_code = f.read()

# Replace boot_id in `process_edge_sync_batch`
main_code = main_code.replace(
"""                    "boot_id": batch.edge_id,""",
"""                    "boot_id": batch.boot_id,"""
)

# And `EdgeService.sequence_number restarts at 0 on every boot` issue?
# Actually the comment says: "Frames restored from disk after a restart are currently re-sent under the new boot's ID, which is also wrong."
# To fix this:
# "Store "boot_id": batch.boot_id, and better still, stamp boot_id on each payload when the frame is captured."
# We should stamp `boot_id` into `EdgePayload` directly!

with open("main.py", "w") as f:
    f.write(main_code)
