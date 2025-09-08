QWEN_25_VL_INSTRUCT_PROMPT = (
    "<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n"
    "<|im_start|>user\n<|vision_start|><|image_pad|><|vision_end|>"
    "{instruction}<|im_end|>\n"
    "<|im_start|>assistant\n"
)

INSTRUCTION = """
Extract the data from this invoice.
Return your response as a valid JSON object.

Here's an example of the expected JSON output: 

{
    "invoiced_date": 09/04/2025  # format DD/MM/YYYY
    "due_date": 09/04/2025  # format DD/MM/YYYY
    "from_info": {
        "email": "jeremya@gmail.com",
        "phone_number": "+33645789564",
        "address": {
            "street": "Chemin des boulangers",
            "city": "Bourges",
            "country": FR # 2 letters country
        },
    "to_info": {
        "email": "igordosgor@gmail.com",
        "phone_number": "+33645789564",
        "address": {
            "street": "Chemin des boulangers",
            "city": "New York",
            "country": US
        },
    }
    "amount": {
        "sub_total": 1450.4 # Before taxes
        "total": 1740.48 # After taxes
        "vat": 0.2 # Pourcentage
        "currency": USD # 3 letters code (USD, EUR, ...)
    }
}
""".strip()
