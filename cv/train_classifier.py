"""Обучение MobileNetV2 на датасете болезней яблони (подпапки = классы)."""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms, models
from PIL import Image
import os
from typing import Tuple, List
import json

from cv.labels_config import default_class_labels_for_crop

DEFAULT_CLASS_LABELS = default_class_labels_for_crop("apple")


class AppleDataset(Dataset):
    """Датасет: подпапки = классы; индексы совпадают с DEFAULT_CLASS_LABELS."""

    def __init__(self, root_dir: str, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.class_labels = list(DEFAULT_CLASS_LABELS)
        self.image_paths = []
        self.labels = []

        for idx, class_name in enumerate(self.class_labels):
            class_dir = os.path.join(root_dir, class_name)
            if not os.path.isdir(class_dir):
                continue
            for img_name in os.listdir(class_dir):
                if img_name.lower().endswith((".png", ".jpg", ".jpeg")):
                    self.image_paths.append(os.path.join(class_dir, img_name))
                    self.labels.append(idx)

        print(f"Загружено {len(self.image_paths)} изображений, классов: {len(self.class_labels)}")
        print(f"Классы: {self.class_labels}")

    # Возвращает число образцов в датасете.
    def __len__(self):
        return len(self.image_paths)

    # Возвращает пару (тензор изображения, индекс класса) по индексу.
    def __getitem__(self, idx):
        img_path = self.image_paths[idx]
        image = Image.open(img_path).convert('RGB')
        label = self.labels[idx]

        if self.transform:
            image = self.transform(image)

        return image, label


# Обучает MobileNetV2 на train/val и сохраняет лучшую модель в save_path.
def train_model(
    train_dir: str,
    val_dir: str,
    num_classes: int,
    epochs: int = 25,
    batch_size: int = 32,
    learning_rate: float = 0.001,
    save_path: str = 'apple_classifier.pth'
):

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    train_dataset = AppleDataset(train_dir, transform=train_transform)
    val_dataset = AppleDataset(val_dir, transform=val_transform)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=4)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=4)

    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    last_channel = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.2),
        nn.Linear(last_channel, num_classes)
    )

    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=7, gamma=0.1)

    best_val_acc = 0.0

    for epoch in range(epochs):
        print(f'\nEpoch {epoch+1}/{epochs}')
        print('-' * 30)

        model.train()
        running_loss = 0.0
        running_corrects = 0

        for inputs, labels in train_loader:
            inputs = inputs.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()

            with torch.set_grad_enabled(True):
                outputs = model(inputs)
                _, preds = torch.max(outputs, 1)
                loss = criterion(outputs, labels)

                loss.backward()
                optimizer.step()

            running_loss += loss.item() * inputs.size(0)
            running_corrects += torch.sum(preds == labels.data)

        epoch_loss = running_loss / len(train_dataset)
        epoch_acc = running_corrects.double() / len(train_dataset)

        print(f'Train Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}')

        model.eval()
        val_loss = 0.0
        val_corrects = 0

        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs = inputs.to(device)
                labels = labels.to(device)

                outputs = model(inputs)
                _, preds = torch.max(outputs, 1)
                loss = criterion(outputs, labels)

                val_loss += loss.item() * inputs.size(0)
                val_corrects += torch.sum(preds == labels.data)

        val_epoch_loss = val_loss / len(val_dataset)
        val_epoch_acc = val_corrects.double() / len(val_dataset)

        print(f'Val Loss: {val_epoch_loss:.4f} Acc: {val_epoch_acc:.4f}')

        if val_epoch_acc > best_val_acc:
            best_val_acc = val_epoch_acc
            torch.save({
                'epoch': epoch,
                'state_dict': model.state_dict(),
                'class_labels': train_dataset.class_labels,
                'val_acc': val_epoch_acc
            }, save_path)
            print(f'Model saved to {save_path}')

        scheduler.step()

    print(f"\nОбучение завершено. Лучшая точность на val: {best_val_acc:.4f}")
    return model


if __name__ == "__main__":
    """
    train_model(
        train_dir='data/train',
        val_dir='data/val',
        num_classes=10,
        epochs=25,
        batch_size=32,
        learning_rate=0.001,
        save_path='apple_classifier.pth'
    )
    """
    print("Укажите пути train/val и раскомментируйте вызов train_model().")