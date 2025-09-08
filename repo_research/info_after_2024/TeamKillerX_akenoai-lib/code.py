from akenoai import AkenoXToJs

js = AkenoXToJs()

prompt = """
Lukisan airbrush abstrak setengah badan seorang pria Korea dengan rambut hitam berantakan,
mengenakan topeng hacker keren.
Jaket baseball merah dan putih bertuliskan 'MONYET' terlihat jelas. Gaya kontemporer, warna biru, kuning, dengan sentuhan sepia,
detail kode Python terukir di topeng
"""

response = await js.randydev.image.create(
    "black-forest-labs/flux-1-schnell",
    api_key="here", # @aknuserbot get api key
    image_read=True,
    query=prompt

file_path = "randydev.jpg"
with open(file_path, "wb") as f:
       f.write(response)
await message.reply_photo(file_path)
