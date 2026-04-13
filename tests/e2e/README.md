# Backend E2E

Calisma sirasi:

1. `../servis_now_dev_env/docker-compose.dev.yml` ile stack ayakta olsun.
2. `scripts/reset_e2e_db.sh` ile DB reset + seed uygula.
3. `E2E_BASE_URL=http://localhost:8000 pytest -m e2e`

Bu suite sadece backend API smoke testleri icindir.
