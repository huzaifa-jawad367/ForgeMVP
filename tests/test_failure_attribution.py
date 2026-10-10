import unittest

from app.schema.contracts import FailureSubsystem
from app.incidents.trigger_rules import TriggerConfig, attribute_root_cause


class TestFailureAttribution(unittest.TestCase):
    def setUp(self):
        self.config = TriggerConfig(
            blur_threshold=50.0,
            noise_threshold=1.0,
            min_brightness=50.0,
            baseline_inference_time_ms=20.0,
            max_gpu_utilization=98.0,
            max_ack_age=10.0,
        )

    def test_camera_disconnect(self):
        metrics = {
            "fps": 0,
            "seconds_since_last_frame": 3.5,
            "pipeline_active": True,
        }
        result = attribute_root_cause(metrics, self.config)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], FailureSubsystem.CAMERA_DISCONNECT)

    def test_optical_defocus(self):
        metrics = {
            "anomaly_score": 0.85,
            "blur_score": 30.0,  # Below 50.0 threshold
        }
        result = attribute_root_cause(metrics, self.config)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], FailureSubsystem.OPTICAL_DEFOCUS)

    def test_optical_sensor_noise(self):
        metrics = {
            "anomaly_score": 0.60,
            "noise_score": 1.5,  # Above 1.0 threshold
        }
        result = attribute_root_cause(metrics, self.config)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], FailureSubsystem.OPTICAL_SENSOR_NOISE)

    def test_environmental_lighting(self):
        metrics = {
            "brightness": 40.0,  # Below 50.0 threshold
        }
        result = attribute_root_cause(metrics, self.config)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], FailureSubsystem.ENVIRONMENTAL_LIGHTING)

    def test_model_inference_stall(self):
        metrics = {
            "inference_time_ms": 75.0,  # > 3 * 20.0
            "cpu_percent": 50.0,
            "gpu_utilization": 60.0,
        }
        result = attribute_root_cause(metrics, self.config)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], FailureSubsystem.MODEL_INFERENCE_STALL)

    def test_hardware_gpu_exhaustion_util(self):
        metrics = {
            "gpu_utilization": 99.0,  # >= 98.0
        }
        result = attribute_root_cause(metrics, self.config)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], FailureSubsystem.HARDWARE_GPU_EXHAUSTION)

    def test_hardware_gpu_exhaustion_temp(self):
        metrics = {
            "gpu_utilization": 50.0,
            "gpu_temperature": 90.0,  # >= 85.0
        }
        result = attribute_root_cause(metrics, self.config)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], FailureSubsystem.HARDWARE_GPU_EXHAUSTION)

    def test_network_partition(self):
        metrics = {
            "ack_age": 15.0,  # > 10.0
        }
        result = attribute_root_cause(metrics, self.config)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], FailureSubsystem.NETWORK_PARTITION)

    def test_no_attribution(self):
        metrics = {
            "fps": 10,
            "seconds_since_last_frame": 0.1,
            "pipeline_active": True,
            "anomaly_score": 0.2,
            "blur_score": 80.0,
            "noise_score": 0.5,
            "brightness": 120.0,
            "inference_time_ms": 15.0,
            "cpu_percent": 30.0,
            "gpu_utilization": 40.0,
            "gpu_temperature": 50.0,
            "ack_age": 1.0,
        }
        result = attribute_root_cause(metrics, self.config)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
