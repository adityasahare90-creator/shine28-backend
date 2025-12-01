Shine28 Full Backend (Render-ready)

ENV:
SHINE28_ADMIN_PW=shine28@1986
SHINE28_SECRET=some-long-secret

Start locally:
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app_api.py

Deploy: upload to Render/GCP/Heroku/Railway. Start command: python app_api.py
Admin UI: /admin
