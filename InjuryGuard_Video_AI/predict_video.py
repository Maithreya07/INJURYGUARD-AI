import os
import cv2
import torch
import torch.nn as nn
from torchvision import models, transforms

# -----------------------------
# SETTINGS
# -----------------------------

MODEL_PATH = "video_model.pth"

CLASSES = ["walking", "running", "kicking"]

NUM_FRAMES = 8

DEVICE = torch.device("cpu")


# -----------------------------
# LOAD MODEL
# -----------------------------

print("Loading model...")

model = models.mobilenet_v3_small(weights=None)

model.classifier[3] = nn.Linear(
    model.classifier[3].in_features,
    len(CLASSES)
)

model.load_state_dict(
    torch.load(MODEL_PATH, map_location=DEVICE)
)

model = model.to(DEVICE)

model.eval()


# -----------------------------
# IMAGE TRANSFORM
# -----------------------------

transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


# -----------------------------
# PREDICT VIDEO
# -----------------------------

def predict_video(video_path):

    print("\nVideo:", video_path)

    cap = cv2.VideoCapture(video_path)

    total_frames = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    if total_frames <= 0:
        print("Could not read video.")
        return

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

    if len(frames) == 0:
        print("No frames found.")
        return

    frames = torch.stack(frames)

    frames = frames.to(DEVICE)

    with torch.no_grad():

        outputs = model(frames)

        # Average predictions from all frames
        outputs = outputs.mean(dim=0)

        predicted_class = outputs.argmax().item()

    print("\n==============================")
    print("VIDEO MOVEMENT RESULT")
    print("==============================")

    print(
        "Detected movement:",
        CLASSES[predicted_class]
    )

    print("==============================")


# -----------------------------
# MAIN
# -----------------------------

video_path = input(
    "\nEnter video path: "
).strip().strip('"')

if os.path.exists(video_path):

    predict_video(video_path)

else:

    print("\nVideo file not found.")