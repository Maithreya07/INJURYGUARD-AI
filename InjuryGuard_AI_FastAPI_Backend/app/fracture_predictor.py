import os
import torch
from torch import nn
from PIL import Image, ImageFile
from torchvision import transforms, models

# Allow truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

# -----------------------------
# 1. Model path
# -----------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "fracture_model.pth"
)


# -----------------------------
# 2. Device
# -----------------------------

device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# -----------------------------
# 3. Create model
# -----------------------------

model = models.resnet18(
    weights=None
)

model.fc = nn.Linear(
    model.fc.in_features,
    2
)


# -----------------------------
# 4. Load trained model
# -----------------------------

model.load_state_dict(
    torch.load(
        MODEL_PATH,
        map_location=device
    )
)

model = model.to(device)

model.eval()


# -----------------------------
# 5. Image preprocessing
# -----------------------------

transform = transforms.Compose([
    transforms.Resize((224, 224)),

    transforms.Grayscale(
        num_output_channels=3
    ),

    transforms.ToTensor(),

    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


# -----------------------------
# 6. Prediction function
# -----------------------------

def predict_fracture(image_path):

    image = Image.open(
        image_path
    ).convert("L")

    image_tensor = transform(
        image
    )

    image_tensor = image_tensor.unsqueeze(0)

    image_tensor = image_tensor.to(device)


    # Model prediction
    with torch.no_grad():

        output = model(
            image_tensor
        )

        probabilities = torch.softmax(
            output,
            dim=1
        )

        confidence, predicted = torch.max(
            probabilities,
            1
        )


    predicted_class = predicted.item()

    confidence_value = (
        confidence.item() * 100
    )


    # Class name
    if predicted_class == 1:

        prediction = "FRACTURED"

    else:

        prediction = "NON-FRACTURED"


    return {
        "prediction": prediction,
        "confidence": round(
            confidence_value,
            2
        )
    }