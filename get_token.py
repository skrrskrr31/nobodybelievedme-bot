"""
İlk kez çalıştır → tarayıcıda izin ver → token_nobody.json oluşur
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token_nobody.json", "w") as f:
    f.write(creds.to_json())

print("token_nobody.json oluştu!")
