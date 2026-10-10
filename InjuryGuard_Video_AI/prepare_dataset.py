import os
import random
import shutil

SOURCE = r"C:\Users\ADMIN\Downloads\UCF_Sports\ucf_sports_actions\ucf action"
DEST = r"C:\Users\ADMIN\Downloads\InjuryGuard_Video_AI\dataset"

CLASS_FOLDERS = {
    "walking": ["Walk-Front"],
    "running": ["Run-Side"],
    "kicking": ["Kicking-Front", "Kicking-Side"]
}

TRAIN_COUNT = 9
VALID_COUNT = 2
TEST_COUNT = 2

VIDEO_EXTENSIONS = {".avi", ".mp4", ".mov", ".mpg", ".mpeg"}

random.seed(42)


def find_videos(folder_names):
    videos = []

    for folder_name in folder_names:

        folder_path = os.path.join(SOURCE, folder_name)

        if not os.path.exists(folder_path):
            print(f"Folder not found: {folder_path}")
            continue

        for root, dirs, files in os.walk(folder_path):
            for file in files:

                extension = os.path.splitext(file)[1].lower()

                if extension in VIDEO_EXTENSIONS:
                    videos.append(os.path.join(root, file))

    return videos


for class_name, folder_names in CLASS_FOLDERS.items():

    print(f"\nProcessing: {class_name}")

    videos = find_videos(folder_names)

    random.shuffle(videos)

    print(f"Videos found: {len(videos)}")

    required = TRAIN_COUNT + VALID_COUNT + TEST_COUNT

    if len(videos) < required:
        print(f"Not enough videos for {class_name}")
        continue

    selected = videos[:required]

    train_videos = selected[:TRAIN_COUNT]
    valid_videos = selected[TRAIN_COUNT:TRAIN_COUNT + VALID_COUNT]
    test_videos = selected[TRAIN_COUNT + VALID_COUNT:]

    splits = {
        "train": train_videos,
        "valid": valid_videos,
        "test": test_videos
    }

    for split, split_videos in splits.items():

        destination_folder = os.path.join(
            DEST,
            split,
            class_name
        )

        os.makedirs(destination_folder, exist_ok=True)

        for index, source_file in enumerate(split_videos, start=1):

            extension = os.path.splitext(source_file)[1]

            destination_file = os.path.join(
                destination_folder,
                f"{class_name}_{index:02d}{extension}"
            )

            shutil.copy2(source_file, destination_file)

            print(
                f"  {split}: "
                f"{os.path.basename(source_file)}"
            )


print("\n================================")
print("Dataset preparation completed!")
print("================================")
