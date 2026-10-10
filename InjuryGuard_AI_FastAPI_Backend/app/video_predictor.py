from pathlib import Path

import cv2
import torch
import torch.nn as nn
from torchvision import models, transforms


# ============================================================
# MODEL PATH
# ============================================================

# video_predictor.py is inside:
# InjuryGuard_AI_FastAPI_Backend/app/
#
# parent.parent points to:
# InjuryGuard_AI_FastAPI_Backend/
#
# video_model.pth is located there.

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "video_model.pth"


# ============================================================
# MODEL SETTINGS
# ============================================================

CLASSES = ["walking", "running", "kicking"]

NUM_FRAMES = 8

DEVICE = torch.device("cpu")


# ============================================================
# CHECK MODEL FILE
# ============================================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Video model not found at: {MODEL_PATH}"
    )


# ============================================================
# LOAD MODEL
# ============================================================

model = models.mobilenet_v3_small(weights=None)

model.classifier[3] = nn.Linear(
    model.classifier[3].in_features,
    len(CLASSES)
)

model.load_state_dict(
    torch.load(
        MODEL_PATH,
        map_location=DEVICE
    )
)

model = model.to(DEVICE)
model.eval()


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

transform = transforms.Compose([
    transforms.ToPILImage(),

    transforms.Resize((224, 224)),

    transforms.ToTensor(),

    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


# ============================================================
# VIDEO PREDICTION
# ============================================================

def predict_video(video_path: str):

    cap = cv2.VideoCapture(video_path)

    total_frames = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    if total_frames <= 0:
        cap.release()
        raise ValueError("Could not read video")

    frame_positions = torch.linspace(
        0,
        total_frames - 1,
        NUM_FRAMES
    ).long()

    frames = []

    for position in frame_positions:

        cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            int(position)
        )

        success, frame = cap.read()

        if success:

            frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            frame = transform(frame)

            frames.append(frame)

    cap.release()

    if not frames:
        raise ValueError(
            "No frames could be extracted"
        )

    frames = torch.stack(frames)

    frames = frames.to(DEVICE)

    with torch.no_grad():

        outputs = model(frames)

        outputs = outputs.mean(dim=0)

        predicted_index = outputs.argmax().item()

    return {
        "movement": CLASSES[predicted_index]
    }
