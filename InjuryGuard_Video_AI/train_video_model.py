import os
import cv2
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms

# -----------------------------
# SETTINGS
# -----------------------------

DATASET = r"C:\Users\ADMIN\Downloads\InjuryGuard_Video_AI\dataset"

CLASSES = ["walking", "running", "kicking"]

NUM_FRAMES = 8
BATCH_SIZE = 2
EPOCHS = 5

DEVICE = torch.device("cpu")

print("Using device:", DEVICE)


# -----------------------------
# VIDEO DATASET
# -----------------------------

class VideoDataset(Dataset):

    def __init__(self, split):

        self.samples = []

        split_path = os.path.join(DATASET, split)

        for label, class_name in enumerate(CLASSES):

            class_path = os.path.join(split_path, class_name)

            for file in os.listdir(class_path):

                if file.lower().endswith((".avi", ".mp4", ".mov", ".mpg", ".mpeg")):

                    video_path = os.path.join(class_path, file)

                    self.samples.append((video_path, label))

        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

        print(split, "videos:", len(self.samples))


    def __len__(self):
        return len(self.samples)


    def __getitem__(self, index):

        video_path, label = self.samples[index]

        cap = cv2.VideoCapture(video_path)

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        frames = []

        if total_frames <= 0:
            total_frames = NUM_FRAMES

        frame_positions = torch.linspace(
            0,
            max(total_frames - 1, 0),
            NUM_FRAMES
        ).long()

        for position in frame_positions:

            cap.set(cv2.CAP_PROP_POS_FRAMES, int(position))

            success, frame = cap.read()

            if success:

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                frame = self.transform(frame)

                frames.append(frame)

            else:

                frames.append(
                    torch.zeros(3, 224, 224)
                )

        cap.release()

        frames = torch.stack(frames)

        return frames, torch.tensor(label)


# -----------------------------
# DATA LOADERS
# -----------------------------

train_dataset = VideoDataset("train")
valid_dataset = VideoDataset("valid")
test_dataset = VideoDataset("test")

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True
)

valid_loader = DataLoader(
    valid_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False
)

test_loader = DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False
)


# -----------------------------
# MODEL
# -----------------------------

print("\nLoading MobileNetV3...")

model = models.mobilenet_v3_small(weights="DEFAULT")

# Freeze the main network
for parameter in model.features.parameters():
    parameter.requires_grad = False

# Change final classifier
model.classifier[3] = nn.Linear(
    model.classifier[3].in_features,
    len(CLASSES)
)

model = model.to(DEVICE)


# -----------------------------
# TRAINING
# -----------------------------

criterion = nn.CrossEntropyLoss()

optimizer = torch.optim.Adam(
    model.classifier[3].parameters(),
    lr=0.001
)


def evaluate(loader):

    model.eval()

    correct = 0
    total = 0

    with torch.no_grad():

        for videos, labels in loader:

            videos = videos.to(DEVICE)
            labels = labels.to(DEVICE)

            batch_size, frames, channels, height, width = videos.shape

            # Combine all frames into one batch
            videos = videos.view(
                batch_size * frames,
                channels,
                height,
                width
            )

            outputs = model(videos)

            # Restore video dimension
            outputs = outputs.view(
                batch_size,
                frames,
                len(CLASSES)
            )

            # Average frame predictions
            outputs = outputs.mean(dim=1)

            predictions = outputs.argmax(dim=1)

            correct += (predictions == labels).sum().item()
            total += labels.size(0)

    return correct / total


print("\nStarting training...\n")

for epoch in range(EPOCHS):

    model.train()

    running_loss = 0

    for videos, labels in train_loader:

        videos = videos.to(DEVICE)
        labels = labels.to(DEVICE)

        batch_size, frames, channels, height, width = videos.shape

        videos = videos.view(
            batch_size * frames,
            channels,
            height,
            width
        )

        outputs = model(videos)

        outputs = outputs.view(
            batch_size,
            frames,
            len(CLASSES)
        )

        outputs = outputs.mean(dim=1)

        loss = criterion(outputs, labels)

        optimizer.zero_grad()

        loss.backward()

        optimizer.step()

        running_loss += loss.item()

    validation_accuracy = evaluate(valid_loader)

    print(
        f"Epoch {epoch + 1}/{EPOCHS} "
        f"- Loss: {running_loss / len(train_loader):.4f} "
        f"- Validation Accuracy: {validation_accuracy * 100:.2f}%"
    )


# -----------------------------
# TEST
# -----------------------------

test_accuracy = evaluate(test_loader)

print("\n================================")
print("Final Test Accuracy:")
print(f"{test_accuracy * 100:.2f}%")
print("================================")


# -----------------------------
# SAVE MODEL
# -----------------------------

torch.save(
    model.state_dict(),
    "video_model.pth"
)

print("\nModel saved as:")
print("video_model.pth")