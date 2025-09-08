import os

cache_path = 'C:\hg_models'  

# Set environment variables
os.environ["TRANSFORMERS_CACHE"] = cache_path
os.environ["HF_HUB_CACHE"] = cache_path
os.environ["HF_HOME"] = cache_path

from PIL import Image
from diffusers import ControlNetModel, StableDiffusionXLControlNetPipeline
from diffusers.utils import make_image_grid, load_image
from transformers import AutoImageProcessor
import torch
import cv2  # for Canny edge detection


# Define paths and settings
controlnet_model_id = "xinsir/controlnet-canny-sdxl-1.0"
model_id = "SG161222/RealVisXL_V4.0"
output_dir = "0-Assets/output"
os.makedirs(output_dir, exist_ok=True)

# Load ControlNet model
controlnet = ControlNetModel.from_pretrained(controlnet_model_id, torch_dtype=torch.float16)
pipe = StableDiffusionXLControlNetPipeline.from_pretrained(
    model_id,
    controlnet=controlnet,
    torch_dtype=torch.float16
)

# define device
if torch.cuda.is_available():
    device = "cuda"
    print("Using CUDA")

elif torch.backends.mps.is_available():
    device = "mps"
    print("Using MPS ")

else:
    device = "cpu"
    print("Using CPU - this can take hours xD")

pipe = pipe.to(device)
# speed up inference
pipe.enable_model_cpu_offload()

# Prepare Canny edge detection input
input_image_path = "0-Assets/rhino_capture.jpg"  # Replace with your image path
image = cv2.imread(input_image_path, cv2.IMREAD_GRAYSCALE)
low_threshold = 100
high_threshold = 200
edges = cv2.Canny(image, low_threshold, high_threshold)
edges_pil = Image.fromarray(edges)

# Define prompt and settings
prompt = (
    "a stunning view of a cluster of modular pavilions nestled within the lush Brazilian jungle, the roof is built using woven bamboo elements, surrounded by majestic mountains rising in the background and a serene river flowing in the foreground, the trees are way taller than the pavilions, earthy tones that blend harmoniously with the yellowish greens of the surrounding jungle, volumetric sunlight goes across the jungle, creating fascinating light rays, 4k, high resolution, realistic render, architectural visualization"
)
negative_prompt = "low res, bad quality"

# Generate image with ControlNet
generated_image = pipe(
    prompt=prompt,
    negative_prompt=negative_prompt,
    image=edges_pil,
    guidance_scale=5,
    num_inference_steps=25,
    height=1024,
    width=1024,
    controlnet_conditioning_scale = 0.6,
).images[0]

# Save the generated image
output_image_path = f"{output_dir}/generated_image_1.png"
generated_image.save(output_image_path)
generated_image.show()
image_grid = make_image_grid([edges_pil, generated_image], rows=1, cols=2)
image_grid.show()
