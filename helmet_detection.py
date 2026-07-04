import os
from inference_sdk import InferenceHTTPClient

# Initialize Roboflow client
CLIENT = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key=os.environ.get("ROBOFLOW_API_KEY")
)

MODEL_ID = "face-with-helmet-detection/3"

def detect_helmet_violation(image_path):
    """
    Model: face-with-helmet-detection/3
    Classes: 'With Helmet', 'Without Helmet'
    Violation = 'Without Helmet' detected with confidence >= 0.65
    """
    result = CLIENT.infer(image_path, model_id=MODEL_ID)
    predictions = result.get("predictions", [])

    # print("Raw predictions:", predictions)
    print("Raw predictions:", [(p["class"], round(p["confidence"], 2)) for p in predictions])

    violations = [
        p for p in predictions
        if p.get("class", "").lower() == "without helmet"
        and p.get("confidence", 0) >= 0.65
    ]

    return {
        "violation_detected": len(violations) > 0,
        "confidence": max((v["confidence"] for v in violations), default=0.0),
        "detections": predictions,
        "all_labels": [p.get("class") for p in predictions]
    }