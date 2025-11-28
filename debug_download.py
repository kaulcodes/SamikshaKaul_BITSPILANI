from app.downloader import download_document
import sys

# The ZIP URL from the organizer's text
zip_url = "https://hackrx.blob.core.windows.net/files/TRAINING_SAMPLES.zip?sv=2025-07-05&spr=https&st=2025-11-28T06%3A47%3A35Z&se=2025-11-29T06%3A47%3A35Z&sr=b&sp=r&sig=yB8R2zjoRL2%2FWRuv7E1lvmWSHAkm%2FoIGsepj2Io9pak%3D"

print(f"Attempting to download ZIP: {zip_url}")
try:
    path = download_document(zip_url)
    print(f"SUCCESS! Downloaded to: {path}")
except Exception as e:
    print(f"FAILURE! Error: {e}")
    sys.exit(1)
