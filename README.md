# Stok Takip

Basit Streamlit tabanlı stok takip uygulaması.

Hızlı deploy (Streamlit Cloud):

1. Bu klasörü bir GitHub reposuna pushlayın.
2. GitHub repo URL'siyle https://share.streamlit.io/ adresine gidin.
3. "New app" -> repo ve `app.py` seçin -> Deploy.

Notlar:
- Veritabanı `stok.db` yerel dosyadır; Streamlit Cloud üzerinde dosya sistemi ephemeral olabilir. Kalıcı veri için bir dış veritabanı (Postgres, SQLite dosyasını buluta koyma vb.) kullanın.
- Gereken paketler `requirements.txt` içinde listelenmiştir.
