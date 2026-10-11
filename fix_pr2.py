with open("app/edge/buffer.py", "r") as f:
    code = f.read()

# Add boot_id to EdgePayload
code = code.replace(
"""    payload_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    frame_index: int = 0""",
"""    payload_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    boot_id: str = ""
    frame_index: int = 0"""
)

with open("app/edge/buffer.py", "w") as f:
    f.write(code)

with open("app/edge/service.py", "r") as f:
    code = f.read()

# Pass boot_id to EdgePayload
code = code.replace(
"""            payload = EdgePayload(
                payload_id=str(uuid.uuid4()),
                frame_index=frame_counter,""",
"""            payload = EdgePayload(
                payload_id=str(uuid.uuid4()),
                boot_id=self.boot_id,
                frame_index=frame_counter,"""
)

with open("app/edge/service.py", "w") as f:
    f.write(code)

with open("main.py", "r") as f:
    main_code = f.read()

# Use frame's boot_id if available, fallback to batch.boot_id
main_code = main_code.replace(
"""                    "boot_id": batch.boot_id,""",
"""                    "boot_id": frame.get("boot_id", batch.boot_id),"""
)

with open("main.py", "w") as f:
    f.write(main_code)
