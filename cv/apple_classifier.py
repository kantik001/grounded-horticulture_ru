import io
import json
from typing import Any, Dict, List, Optional

import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

from cv.labels_config import default_class_labels_for_crop

# Метки яблони из config/cv_class_labels.json (если в checkpoint нет class_labels).
DEFAULT_CLASS_LABELS = default_class_labels_for_crop("apple")


class AppleClassifier:
    """Классификатор болезней яблони на MobileNetV2 (inference по файлу или байтам)."""

    # Инициализирует устройство, метки классов, загружает веса и задаёт преобразования для 224×224.
    def __init__(
        self,
        model_path: Optional[str] = None,
        num_classes: int = 10,
    ):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.class_labels: List[str] = list(DEFAULT_CLASS_LABELS)
        self.num_classes = num_classes
        checkpoint = self._read_checkpoint(model_path)
        if checkpoint:
            labels = checkpoint.get("class_labels")
            if isinstance(labels, list) and labels:
                self.class_labels = [str(x) for x in labels]
                self.num_classes = len(self.class_labels)
        self.model = self._build_model(checkpoint)
        self.model.to(self.device)
        self.model.eval()
        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        )

    # Читает checkpoint .pth с диска; при ошибке или отсутствии пути возвращает None.
    def _read_checkpoint(self, model_path: Optional[str]) -> Optional[dict]:
        if not model_path:
            return None
        try:
            return torch.load(
                model_path,
                map_location=self.device,
                weights_only=False,
            )
        except Exception:
            return None

    # Собирает MobileNetV2 с головой на num_classes и подставляет state_dict из checkpoint, если есть.
    def _build_model(self, checkpoint: Optional[dict]) -> nn.Module:
        model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
        last_channel = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(p=0.2),
            nn.Linear(last_channel, self.num_classes),
        )
        if checkpoint and "state_dict" in checkpoint:
            model.load_state_dict(checkpoint["state_dict"])
        return model

    # Классифицирует изображение по пути к файлу; возвращает словарь success/prediction/confidence.
    def predict(self, image_path: str) -> Dict[str, Any]:
        try:
            image = Image.open(image_path).convert("RGB")
            image_tensor = self.transform(image).unsqueeze(0).to(self.device)
            return self._run_inference(image_tensor)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "image_processed": False,
            }

    # Классифицирует изображение из байтов (HTTP multipart); формат ответа как у predict.
    def predict_from_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            image_tensor = self.transform(image).unsqueeze(0).to(self.device)
            return self._run_inference(image_tensor)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "image_processed": False,
            }

    # Прогон тензора через модель: softmax, лучший класс и top-3 с уверенностями.
    def _run_inference(self, image_tensor: torch.Tensor) -> Dict[str, Any]:
        with torch.no_grad():
            outputs = self.model(image_tensor)
            probabilities = torch.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probabilities, 1)

        pred_idx = predicted.item()
        if pred_idx >= len(self.class_labels):
            return {
                "success": False,
                "error": f"индекс класса {pred_idx} вне списка меток",
                "image_processed": False,
            }
        top_probs, top_indices = torch.topk(
            probabilities, min(3, len(self.class_labels))
        )
        top_predictions = [
            {
                "label": self.class_labels[idx.item()],
                "confidence": prob.item(),
            }
            for idx, prob in zip(top_indices[0], top_probs[0])
            if idx.item() < len(self.class_labels)
        ]

        return {
            "success": True,
            "prediction": self.class_labels[pred_idx],
            "confidence": confidence.item(),
            "top_predictions": top_predictions,
            "image_processed": True,
        }


# Фабрика: создаёт AppleClassifier с опциональным путём к обученным весам .pth.
def create_classifier(model_path: str = None) -> AppleClassifier:
    return AppleClassifier(model_path=model_path)


if __name__ == "__main__":
    classifier = create_classifier()
    result = classifier.predict("test_apple.jpg")
    print(json.dumps(result, indent=2))
