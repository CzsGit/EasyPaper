import io
import logging

from PIL import Image

# Surya imports
from surya.layout import batch_layout_detection
from surya.model.detection.segformer import load_model, load_processor

logger = logging.getLogger(__name__)


class LayoutAnalyzer:
    def __init__(self):
        self.model = None
        self.processor = None

    def load_model(self):
        if self.model is not None:
            return

        try:
            # Load Surya model and processor
            # Checkpoint "vikp/surya_layout2" is the default high-acc model
            self.model = load_model(checkpoint="vikp/surya_layout2")
            self.processor = load_processor(checkpoint="vikp/surya_layout2")
            logger.info("Loaded Surya Layout Analysis model")
        except Exception as e:
            logger.error(f"Failed to load Surya model: {e}")

    def analyze(self, image_bytes: bytes) -> list[dict]:
        """
        Analyze PDF page image and return bounding boxes.
        """
        if self.model is None:
            self.load_model()
            if self.model is None:
                return []

        # Convert bytes to PIL Image
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            return []

        # Inference
        try:
            # batch_layout_detection expects a list of images
            results = batch_layout_detection([image], self.model, self.processor)
            result = results[0]  # We only sent one image
        except Exception as e:
            logger.error(f"Surya inference failed: {e}")
            return []

        output = []
        # Surya result.bboxes is a list of LayoutBox objects
        # LayoutBox has: bbox, label, confidence (maybe)
        # Check Surya output format:
        # result is a LayoutResult object, containing .bboxes (list of LayoutBox)
        # LayoutBox attributes: bbox (list [x1, y1, x2, y2]), label (str), polygon (list)

        for box in result.bboxes:
            x1, y1, x2, y2 = box.bbox
            label = box.label

            # Surya labels: Caption, Footnote, Formula, List-item, Page-footer, Page-header, Picture, Section-header, Table, Text, Title
            # Map to our needs
            if label == "Picture":
                label = "Figure"

            output.append(
                {
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "score": 1.0,  # Surya doesn't always return confidence per box in simple API, assume high
                    "label": label,
                }
            )

        return output
