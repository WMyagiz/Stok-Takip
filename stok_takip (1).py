import streamlit as st
import sqlite3
import pandas as pd
import time
import urllib.parse

# Veritabanı bağlantısı ve tablo oluşturma
def init_db():
    conn = sqlite3.connect('stok.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            price REAL,            currency TEXT DEFAULT '₺',            quantity INTEGER,
            unit TEXT DEFAULT 'Adet',
            reorder_level INTEGER DEFAULT 5
        )
    ''')
    # Bildirimler için tablo
    c.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            message TEXT,
            seen INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    ''')
    conn.commit()
    conn.close()

    # Eğer varolan tablo eski şemadaysa eksik sütunları ekle (güncelleme sonrası uyumluluk)
    conn = sqlite3.connect('stok.db')
    c = conn.cursor()
    c.execute("PRAGMA table_info(products)")
    cols = [r[1] for r in c.fetchall()]
    if 'currency' not in cols:
        try:
            c.execute("ALTER TABLE products ADD COLUMN currency TEXT DEFAULT '₺'")
        except Exception:
            pass
    if 'unit' not in cols:
        try:
            c.execute("ALTER TABLE products ADD COLUMN unit TEXT DEFAULT 'Adet'")
        except Exception:
            pass
    if 'reorder_level' not in cols:
        try:
            c.execute("ALTER TABLE products ADD COLUMN reorder_level INTEGER DEFAULT 5")
        except Exception:
            pass
    conn.commit()
    conn.close()


def add_notification(product_id, message):
    conn = sqlite3.connect('stok.db')
    c = conn.cursor()
    c.execute("INSERT INTO notifications (product_id, message, seen, created_at) VALUES (?, ?, 0, datetime('now'))", (product_id, message))
    conn.commit()
    conn.close()


def get_notifications():
    conn = sqlite3.connect('stok.db')
    df = pd.read_sql_query("SELECT n.id, n.product_id, n.message, n.seen, n.created_at, p.name as product_name FROM notifications n LEFT JOIN products p ON n.product_id = p.id ORDER BY n.created_at DESC", conn)
    conn.close()
    return df


def mark_notification_seen(nid):
    conn = sqlite3.connect('stok.db')
    c = conn.cursor()
    # Bildirim işaretlendiğinde kaydı tamamen sil
    c.execute("DELETE FROM notifications WHERE id=?", (nid,))
    conn.commit()
    conn.close()


def clear_notifications():
    """Veritabanındaki tüm bildirimleri siler."""
    conn = sqlite3.connect('stok.db')
    c = conn.cursor()
    c.execute("DELETE FROM notifications")
    conn.commit()
    conn.close()


def check_low_stock(threshold=5):
    # Her çalıştırmada düşük stoklu ürünler için bildirim ekle (ürün bazlı reorder_level kullan)
    conn = sqlite3.connect('stok.db')
    c = conn.cursor()
    c.execute("SELECT id, name, quantity, reorder_level FROM products")
    rows = c.fetchall()
    for pid, name, qty, rlevel in rows:
        if qty is None:
            continue
        use_threshold = rlevel if (rlevel is not None and rlevel >= 0) else threshold
        if qty <= use_threshold:
            # zaten görülmemüş bir bildirim var mı kontrol et
            c.execute("SELECT COUNT(1) FROM notifications WHERE product_id=? AND seen=0", (pid,))
            exists = c.fetchone()[0]
            if exists == 0:
                msg = f"'{name}' ürün stoğu {qty} oldu — satın alım yapmalısınız."
                c.execute("INSERT INTO notifications (product_id, message, seen, created_at) VALUES (?, ?, 0, datetime('now'))", (pid, msg))
    conn.commit()
    conn.close()


def decrement_stock(product_id, amount):
    conn = sqlite3.connect('stok.db')
    c = conn.cursor()
    c.execute("SELECT quantity, name FROM products WHERE id=?", (product_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, 'Ürün bulunamadı'
    qty, name = row
    new_qty = max(0, qty - amount)
    c.execute("UPDATE products SET quantity=? WHERE id=?", (new_qty, product_id))
    conn.commit()
    # Eğer azaldıysa bildirim ekle (örneğin eşik 5)
    if new_qty <= 5:
        msg = f"'{name}' ürün stoğu {new_qty} oldu — satın alım yapmalısınız."
        c.execute("INSERT INTO notifications (product_id, message, seen, created_at) VALUES (?, ?, 0, datetime('now'))", (product_id, msg))
        conn.commit()
    conn.close()
    return True, new_qty


def add_stock(product_id, amount):
    conn = sqlite3.connect('stok.db')
    c = conn.cursor()
    c.execute("SELECT quantity, name FROM products WHERE id=?", (product_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, 'Ürün bulunamadı'
    qty, name = row
    new_qty = qty + amount
    c.execute("UPDATE products SET quantity=? WHERE id=?", (new_qty, product_id))
    conn.commit()
    conn.close()
    return True, new_qty

# Veritabanından veri okuma
def get_data():
    conn = sqlite3.connect('stok.db')
    df = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()
    return df

# Ürün ekleme fonksiyonu
def add_product(name, category, price, currency, quantity, unit='Adet', reorder_level=5):
    conn = sqlite3.connect('stok.db')
    c = conn.cursor()
    c.execute("INSERT INTO products (name, category, price, currency, quantity, unit, reorder_level) VALUES (?, ?, ?, ?, ?, ?, ?)", (name, category, price, currency, quantity, unit, reorder_level))
    conn.commit()
    conn.close()

# Ürün silme fonksiyonu
def delete_product(id):
    conn = sqlite3.connect('stok.db')
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (id,))
    conn.commit()
    conn.close()

def main():
    st.set_page_config(page_title="Stok Takip Programı", layout="wide", page_icon="📦")
    init_db()
    # Düşük stokları kontrol et ve bildirim oluştur
    check_low_stock()

    # Emoji imleç
    emoji_cursor = '''<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 100 100">
        <text x="50" y="50" font-size="80" text-anchor="middle" dominant-baseline="central">📦</text>
    </svg>'''
    
    cursor_uri = "data:image/svg+xml;utf8," + urllib.parse.quote(emoji_cursor)
    st.markdown(f"""
        <style>
            * {{
                cursor: url('{cursor_uri}') 16 16, auto !important;
            }}
        </style>
    """, unsafe_allow_html=True)

    notifs_df = get_notifications()
    if notifs_df is not None and not notifs_df.empty:
        with st.sidebar.expander(f"🔔 Bildirimler ({len(notifs_df)})", expanded=False):
            # Basit tablo görünümü
            try:
                notif_display = notifs_df[['id', 'product_name', 'message', 'created_at']].copy()
            except Exception:
                notif_display = notifs_df.copy()
            notif_display = notif_display.rename(columns={
                'product_name': 'Ürün', 'message': 'Mesaj', 'created_at': 'Oluşturulma'} )
            st.dataframe(notif_display, use_container_width=True)

            # Tekil silme seçeneği
            sel_id = st.selectbox('Silinecek bildirim', options=notifs_df['id'].tolist(), format_func=lambda x: f"ID: {x} - {notifs_df[notifs_df['id']==x]['product_name'].values[0]} - {notifs_df[notifs_df['id']==x]['created_at'].values[0]}")
            if st.button('Görüldü olarak sil'):
                mark_notification_seen(sel_id)
                st.success('Bildirim silindi')
                st.rerun()

            # Hepsini sil
            if st.button('Tümünü Sil'):
                clear_notifications()
                st.success('Tüm bildirimler silindi')
                st.rerun()

    st.title("📦 Stok Takip Programı")

    menu = ["Gösterge Paneli (Dashboard)", "Ürün Ekle", "Ürünleri Yönet (Düzenle/Sil)"]
    choice = st.sidebar.selectbox("Menü", menu)

    if choice == "Gösterge Paneli (Dashboard)":
        st.subheader("📊 Genel Bakış")
        df = get_data()
        
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Toplam Ürün Çeşidi", len(df))
            with col2:
                # Adet ve Metre olarak ayrı toplamlar
                if 'unit' in df.columns:
                    total_adet = int(df.loc[df['unit'] == 'Adet', 'quantity'].sum())
                    total_metre = float(df.loc[df['unit'] == 'Metre', 'quantity'].sum())
                else:
                    total_adet = int(df['quantity'].sum())
                    total_metre = 0
                st.metric("Toplam Stok (Adet)", total_adet)
                st.metric("Toplam Kablo (Metre)", f"{total_metre:,.2f}")
            with col3:
                # Para birimi bazında toplam stok değeri
                df_val = df.copy()
                df_val['value'] = df_val['price'] * df_val['quantity']
                totals = df_val.groupby('currency')['value'].sum().to_dict()
                tl_total = totals.get('₺', 0.0)
                usd_total = totals.get('$', 0.0)
                eur_total = totals.get('€', 0.0)
                gbp_total = totals.get('£', 0.0)
                # Gösterimler
                st.metric("Toplam Değer (₺)", f"{tl_total:,.2f} ₺")
                st.metric("Toplam Değer ($)", f"{usd_total:,.2f} $")
                st.metric("Toplam Değer (€)", f"{eur_total:,.2f} €")
                if gbp_total:
                    st.metric("Toplam Değer (£)", f"{gbp_total:,.2f} £")
            
            st.divider()
            
            st.subheader("📋 Mevcut Stok Durumu")
            # sütun sırasını belirle ve birimi görünür kıl
            cols_order = ['id','name','category','price','currency','quantity','unit','reorder_level']
            display_df = df[[c for c in cols_order if c in df.columns]]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            st.subheader("📈 Kategori Bazlı Stok Dağılımı (Adet)")
            try:
                category_counts_adet = df[df['unit'] == 'Adet'].groupby('category')['quantity'].sum().reset_index()
            except Exception:
                category_counts_adet = pd.DataFrame(columns=['category','quantity'])
            st.bar_chart(category_counts_adet.set_index('category'))
            
            # Metre bazlı kategori grafiği kaldırıldı; sadece 'Adet' grafiği gösteriliyor

        else:
            st.info("Kayıtlı ürün bulunmamaktadır. Lütfen sol menüden 'Ürün Ekle' kısmına giderek ürün ekleyin.")

    elif choice == "Ürün Ekle":
        st.subheader("➕ Yeni Ürün Ekle")
        # form yerine normal widgetlar kullan (Enter submitini engellemek için)
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Ürün Adı")
            category_list = ["El aletleri", "Elektrik/Elektronik", "Mekanik", "Makine"]
            category = st.selectbox("Kategori", category_list)
        with col2:
            price = st.number_input("Birim Fiyatı", min_value=0.0, format="%.2f")
            currency = st.selectbox("Para Birimi", ["₺", "$", "€", "£"], index=0)
            # birimi adı girdikten sonra ekrana yaz
            unit_preview = 'Metre' if (name and 'kablo' in name.lower()) else 'Adet'
            quantity = st.number_input(f"Stok Miktarı ({unit_preview})", min_value=0, step=1)
            reorder_level = st.number_input("Yeniden Sipariş Eşiği", min_value=0, value=5, step=1)

        if st.button('Ürünü Ekle'):
            if name.strip() == "":
                st.warning("⚠️ Ürün adı boş bırakılamaz!")
            else:
                unit = 'Metre' if 'kablo' in name.lower() else 'Adet'
                add_product(name, category, price, currency, quantity, unit, int(reorder_level))
                st.toast(f"✅ '{name}' başarıyla stoklara eklendi! ({unit} {currency})", icon="🎉")
                st.success(f"✅ '{name}' başarıyla stoklara eklendi!")
                time.sleep(2)

    elif choice == "Ürünleri Yönet (Düzenle/Sil)":
        st.subheader("⚙️ Ürünleri Yönet")
        df = get_data()

        if not df.empty:
            st.write("✏️ Aşağıdaki tablodan verileri doğrudan düzenleyebilirsiniz:")
            
            # Etkileşimli veri düzenleme (Streamlit 1.23+ ile çalışır)
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                hide_index=True,
                key="data_editor",
                num_rows="dynamic"  # Satır ekleme veya silmeye izin verebilir (opsiyonel)
            )

            # Değişiklikleri Kaydet
            if st.button("💾 Değişiklikleri Kaydet"):
                try:
                    conn = sqlite3.connect('stok.db')
                    edited_df.to_sql('products', conn, if_exists='replace', index=False)
                    conn.close()
                    st.success("✅ Tüm değişiklikler başarıyla kaydedildi!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Hata oluştu: {e}")
                
            st.divider()
            
            # Tekil silme işlemi için ayrı bir form
            st.subheader("🗑️ Ürün Sil")
            with st.form(key="delete_form"):
                delete_id = st.selectbox(
                    "Silinecek Ürünü Seçin", 
                    df['id'].tolist(), 
                    format_func=lambda x: f"ID: {x} - {df[df['id']==x]['name'].values[0]}"
                )
                delete_button = st.form_submit_button("❌ Seçili Ürünü Sil")
                if delete_button:
                    deleted_name = df[df['id']==delete_id]['name'].values[0]
                    delete_product(delete_id)
                    st.toast(f"🗑️ '{deleted_name}' başarıyla silindi!", icon="🗑️")
                    st.success("✅ Ürün silindi!")
                    time.sleep(0.5)
                    st.rerun()
            st.divider()
            st.subheader("📦 Stok İşlemleri")
            with st.form(key="adjust_form"):
                adj_id = st.selectbox(
                    "Ürün Seç", 
                    df['id'].tolist(),
                    format_func=lambda x: f"ID: {x} - {df[df['id']==x]['name'].values[0]}"
                )
                operation = st.selectbox("İşlem", ["Ekle", "Çıkar"])
                # seçilen ürünün birimini al
                selected_unit = 'Adet'
                try:
                    if 'unit' in df.columns:
                        selected_unit = df[df['id']==adj_id]['unit'].values[0]
                        if pd.isna(selected_unit):
                            selected_unit = 'Adet'
                except Exception:
                    selected_unit = 'Adet'

                adj_amount = st.number_input(f"Miktar ({selected_unit})", min_value=1, step=1)
                adj_submit = st.form_submit_button("Uygula")
                if adj_submit:
                    if operation == "Çıkar":
                        ok, res = decrement_stock(adj_id, int(adj_amount))
                        msg = f"✅ Stoğunuz güncellendi. Yeni miktar: {res} {selected_unit}"
                    else:
                        ok, res = add_stock(adj_id, int(adj_amount))
                        msg = f"✅ Stoğunuz güncellendi. Yeni miktar: {res} {selected_unit}"
                    if ok:
                        st.success(msg)
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"Hata: {res}")
        else:
            st.info("Yönetilecek ürün bulunmamaktadır.")

if __name__ == '__main__':
    main()
