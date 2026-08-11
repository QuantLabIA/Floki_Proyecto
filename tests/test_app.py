import io
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from datetime import datetime
from pathlib import Path

os.environ["FLOKI_SECRET_KEY"] = "test-secret"
import app as app_module


class FlokiManagerTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.original_db = app_module.app.config["DATABASE"]
        app_module.app.config.update(TESTING=True, DATABASE=self.db_path)
        app_module.init_db()
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.app.config["DATABASE"] = self.original_db
        Path(self.db_path).unlink(missing_ok=True)

    def csrf(self):
        self.client.get("/login")
        with self.client.session_transaction() as sess:
            return sess["csrf_token"]

    def login(self, username="admin", password="admin123"):
        token = self.csrf()
        response = self.client.post(
            "/login",
            data={"username": username, "password": password, "csrf_token": token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as sess:
            return sess["csrf_token"]

    def create_promoter(self, name, token):
        response = self.client.post(
            "/settings/promoters",
            data={"name": name, "csrf_token": token},
            follow_redirects=True,
        )
        self.assertIn(b"Promotor agregado", response.data)
        connection = sqlite3.connect(self.db_path)
        promoter_id = connection.execute(
            "SELECT id FROM promoters WHERE normalized_name=? AND is_common=0",
            (app_module.normalize_text_key(name),),
        ).fetchone()[0]
        connection.close()
        return promoter_id

    def open_cash(self, token):
        response = self.client.post(
            "/cash/open",
            data={"opening_amount": "10.000", "event_name": "Viernes Floki", "event_date": "2026-07-30", "capacity": "300", "csrf_token": token},
            follow_redirects=True,
        )
        self.assertIn(b"Viernes Floki", response.data)

    def test_promoter_files_duplicate_name_and_single_checkin(self):
        token = self.login()
        pablo_id = self.create_promoter("Pablo", token)
        sofia_id = self.create_promoter("Sofía", token)
        self.open_cash(token)

        first_list = "Nombre\nAna Gómez\nJuan Perez\nAna Gómez\n"
        response = self.client.post(
            "/promoter-lists/import",
            data={
                "promoter_id": str(pablo_id),
                "guest_file": (io.BytesIO(first_list.encode("utf-8")), "pablo.csv"),
                "csrf_token": token,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"2 nombres nuevos", response.data)
        self.assertIn(b"1 repetidos", response.data)

        second_list = "Ana Gomez\nLucia Diaz\n"
        response = self.client.post(
            "/promoter-lists/import",
            data={
                "promoter_id": str(sofia_id),
                "guest_file": (io.BytesIO(second_list.encode("utf-8")), "sofia.txt"),
                "csrf_token": token,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"2 nombres nuevos", response.data)

        connection = sqlite3.connect(self.db_path)
        pablo_ana = connection.execute(
            "SELECT id FROM promoter_guests WHERE promoter_id=? AND normalized_name='ana gomez'",
            (pablo_id,),
        ).fetchone()[0]
        sofia_ana = connection.execute(
            "SELECT id FROM promoter_guests WHERE promoter_id=? AND normalized_name='ana gomez'",
            (sofia_id,),
        ).fetchone()[0]
        connection.close()

        response = self.client.post(
            f"/promoter-lists/{pablo_ana}/check-in",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        self.assertIn(b"Ingreso confirmado", response.data)

        response = self.client.post(
            f"/promoter-lists/{sofia_ana}/check-in",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        self.assertIn(b"ya ingres", response.data.lower())
        self.assertIn(b"Pablo", response.data)

        status = self.client.get("/api/status").get_json()
        self.assertEqual(status["people_count"], 1)

        connection = sqlite3.connect(self.db_path)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM guest_checkins").fetchone()[0], 1)
        credited_promoter = connection.execute("SELECT promoter_id FROM guest_checkins").fetchone()[0]
        self.assertEqual(credited_promoter, pablo_id)
        connection.close()

    def test_master_wps_import_common_list_and_qr_rotation(self):
        token = self.login()
        self.open_cash(token)
        master = """[30/7/26, 12:43:26 p. m.] Pablo: CINTIA DÍAZ

Pilar tutti
Ingrid becerra
[30/7/26, 1:29:04 p. m.] Pablo: JAZ BARROSO

Jazmín peralta
Luz avila
[30/7/26, 2:36:27 p. m.] Pablo: Micaela Suárez
Nicolás Becerra
"""
        response = self.client.post(
            "/promoter-lists/import-master",
            data={
                "master_file": (io.BytesIO(master.encode("utf-8")), "lista_wps.txt"),
                "import_mode": "sync",
                "csrf_token": token,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Archivo sincronizado", response.data)

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        promoters = connection.execute(
            "SELECT * FROM promoters WHERE is_common=0 ORDER BY name"
        ).fetchall()
        self.assertEqual([row["name"] for row in promoters], ["CINTIA DÍAZ", "JAZ BARROSO"])
        self.assertEqual(len({row["qr_token"] for row in promoters}), 2)
        self.assertTrue(all(row["qr_token"] for row in promoters))
        common = connection.execute("SELECT * FROM promoters WHERE is_common=1").fetchone()
        self.assertIsNone(common["qr_token"])
        common_guests = connection.execute(
            "SELECT COUNT(*) FROM promoter_guests WHERE promoter_id=?", (common["id"],)
        ).fetchone()[0]
        self.assertEqual(common_guests, 2)
        old_tokens = {row["id"]: row["qr_token"] for row in promoters}
        connection.close()

        response = self.client.post(
            "/cash/close",
            data={"declared_cash": "10.000", "notes": "", "csrf_token": token},
            follow_redirects=True,
        )
        self.assertIn("códigos QR renovados".encode("utf-8"), response.data)

        connection = sqlite3.connect(self.db_path)
        new_tokens = dict(connection.execute("SELECT id, qr_token FROM promoters WHERE is_common=0"))
        connection.close()
        for promoter_id, old_token in old_tokens.items():
            self.assertNotEqual(old_token, new_tokens[promoter_id])

    def test_quick_entry_and_beverage_sales(self):
        token = self.login()
        self.open_cash(token)

        connection = sqlite3.connect(self.db_path)
        connection.execute("UPDATE entry_prices SET before_price=8000, after_price=8000 WHERE category='general'")
        beverage_id = connection.execute("SELECT id FROM beverage_products WHERE beverage_type='Cerveza' ORDER BY id LIMIT 1").fetchone()[0]
        connection.commit()
        connection.close()

        self.client.post(
            "/movements/quick-sale",
            data={
                "sale_kind": "entry",
                "category": "general",
                "quantity": "2",
                "payment_method": "cash",
                "promoter_id": "",
                "csrf_token": token,
            },
            follow_redirects=True,
        )
        self.client.post(
            "/movements/quick-sale",
            data={
                "sale_kind": "beverage",
                "beverage_id": str(beverage_id),
                "quantity": "3",
                "payment_method": "mercadopago",
                "csrf_token": token,
            },
            follow_redirects=True,
        )

        status = self.client.get("/api/status").get_json()
        self.assertEqual(status["sales"], 28000)
        self.assertEqual(status["people_count"], 2)
        connection = sqlite3.connect(self.db_path)
        beverage_payment = connection.execute("SELECT payment_method FROM movements WHERE category='drink' ORDER BY id DESC LIMIT 1").fetchone()[0]
        connection.close()
        self.assertEqual(beverage_payment, "cash")

    def test_cloakroom_stock_and_list_cleanup_on_close(self):
        token = self.login()
        self.open_cash(token)
        connection = sqlite3.connect(self.db_path)
        cloakroom_id = connection.execute("SELECT id FROM ticketing_products WHERE name='Guardarropa'").fetchone()[0]
        beverage_id = connection.execute("SELECT id FROM beverage_products WHERE beverage_type='Cerveza' ORDER BY id LIMIT 1").fetchone()[0]
        promoter_id = connection.execute("SELECT id FROM promoters WHERE is_common=1").fetchone()[0]
        session_id = connection.execute("SELECT id FROM cash_sessions WHERE status='open'").fetchone()[0]
        admin_id = connection.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        stock_id = connection.execute("SELECT id FROM beverage_stock WHERE cash_session_id=? AND beverage_id=?", (session_id, beverage_id)).fetchone()[0]
        connection.execute("UPDATE beverage_stock SET initial_quantity=20 WHERE id=?", (stock_id,))
        connection.execute("INSERT INTO promoter_guests(cash_session_id,promoter_id,guest_name,normalized_name,source_filename,imported_at,imported_by) VALUES (?,?,?,?,?,?,?)", (session_id,promoter_id,'Invitado Test','invitado test','bloc',app_module.now_iso(),admin_id))
        connection.commit(); connection.close()

        self.client.post('/movements/quick-sale', data={'sale_kind':'ticketing_product','ticketing_product_id':cloakroom_id,'quantity':'2','payment_method':'cash','csrf_token':token}, follow_redirects=True)
        self.client.post('/movements/quick-sale', data={'sale_kind':'beverage','beverage_id':beverage_id,'quantity':'3','payment_method':'cash','csrf_token':token}, follow_redirects=True)
        response = self.client.post('/stock/update', data={'session_id':session_id, f'initial_{stock_id}':'20', f'final_{stock_id}':'17', 'csrf_token':token}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        connection = sqlite3.connect(self.db_path)
        self.assertEqual(connection.execute("SELECT COALESCE(SUM(quantity),0) FROM movements WHERE category='cloakroom' AND voided=0").fetchone()[0], 2)
        self.assertEqual(connection.execute("SELECT COALESCE(SUM(quantity),0) FROM movements WHERE beverage_product_id=? AND voided=0", (beverage_id,)).fetchone()[0], 3)
        connection.close()

        response = self.client.post('/cash/close', data={'declared_cash':'24.000','notes':'','csrf_token':token}, follow_redirects=True)
        self.assertIn(b'Se eliminaron', response.data)
        connection = sqlite3.connect(self.db_path)
        self.assertEqual(connection.execute('SELECT COUNT(*) FROM promoter_guests WHERE cash_session_id=?',(session_id,)).fetchone()[0], 0)
        self.assertGreater(connection.execute('SELECT COUNT(*) FROM beverage_stock WHERE cash_session_id=?',(session_id,)).fetchone()[0], 0)
        connection.close()


    def test_rrpp_benefit_special_sale_and_stock_yield(self):
        token = self.login()
        self.open_cash(token)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        trago = connection.execute("SELECT * FROM beverage_products WHERE beverage_type='Trago preparado' ORDER BY id LIMIT 1").fetchone()
        session_id = connection.execute("SELECT id FROM cash_sessions WHERE status='open'").fetchone()[0]
        stock_id = connection.execute("SELECT id FROM beverage_stock WHERE cash_session_id=? AND beverage_id=?", (session_id, trago['id'])).fetchone()[0]
        connection.execute("UPDATE beverage_stock SET initial_quantity=8 WHERE id=?", (stock_id,))
        connection.commit(); connection.close()

        self.client.post('/movements/quick-sale', data={
            'sale_kind':'beverage','beverage_id':trago['id'],'quantity':'5','payment_method':'cash','csrf_token':token
        }, follow_redirects=True)
        response = self.client.post('/movements/quick-sale', data={
            'sale_kind':'rrpp_benefit','beverage_id':trago['id'],'quantity':'2','benefit_price':'6000','csrf_token':token
        }, follow_redirects=True)
        self.assertIn(b'Se descont', response.data)
        response = self.client.post('/movements/quick-sale', data={
            'sale_kind':'special_beverage','beverage_id':trago['id'],'quantity':'3','special_price':'5000',
            'payment_method':'mercadopago','comment':'Promo vaso de fernet','csrf_token':token
        }, follow_redirects=True)
        self.assertIn(b'asignada al stock', response.data)

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        benefit = connection.execute("SELECT * FROM movements WHERE category='rrpp_benefit'").fetchone()
        special = connection.execute("SELECT * FROM movements WHERE category='drink_special'").fetchone()
        self.assertEqual(benefit['total'], 0)
        self.assertIsNone(benefit['promoter_id'])
        self.assertEqual(benefit['quantity'], 1)
        self.assertEqual(benefit['unit_price'], 0)
        self.assertIn('VOUCHER RRPP $0', benefit['description'])
        self.assertIn('Promo vaso de fernet', special['description'])
        self.assertEqual(special['total'], 15000)
        self.assertEqual(special['quantity'], 3)
        self.assertEqual(special['payment_method'], 'cash')
        connection.close()

        response = self.client.post('/stock/update', data={
            'session_id':session_id, f'initial_{stock_id}':'8', f'final_{stock_id}':'6', 'csrf_token':token
        }, follow_redirects=True)
        self.assertIn(b'5.0 vaso / botella', response.data)

    def test_new_beverage_is_added_to_open_event_stock_and_excel(self):
        token = self.login()
        self.open_cash(token)
        response = self.client.post('/settings/beverages', data={
            'beverage_type':'Gin','brand_choice':'Bombay Sapphire','presentation':'vaso',
            'price':'7000','stock_unit':'botella','sort_order':'90','csrf_token':token
        }, follow_redirects=True)
        self.assertIn(b'Variante agregada', response.data)
        connection = sqlite3.connect(self.db_path)
        beverage_id = connection.execute("SELECT id FROM beverage_products WHERE beverage_type='Gin' AND brand='Bombay Sapphire' AND presentation='vaso'").fetchone()[0]
        session_id = connection.execute("SELECT id FROM cash_sessions WHERE status='open'").fetchone()[0]
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM beverage_stock WHERE cash_session_id=? AND beverage_id=?", (session_id, beverage_id)).fetchone()[0], 1)
        connection.close()
        export = self.client.get('/stock/export.xlsx')
        self.assertEqual(export.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(export.data)) as archive:
            self.assertIn(b'Gin Bombay Sapphire', archive.read('xl/worksheets/sheet1.xml'))

        self.client.post(f'/settings/beverages/{beverage_id}/toggle', data={'csrf_token':token}, follow_redirects=True)
        export = self.client.get('/stock/export.xlsx')
        with zipfile.ZipFile(io.BytesIO(export.data)) as archive:
            self.assertNotIn(b'Gin Bombay Sapphire', archive.read('xl/worksheets/sheet1.xml'))

    def test_dashboard_removes_manual_special_cards_and_beverage_order_field(self):
        token = self.login()
        self.open_cash(token)
        page = self.client.get('/')
        self.assertNotIn(b'>Bebida especial<', page.data)
        self.assertNotIn(b'>Venta especial<', page.data)
        self.assertNotIn(b'>Registrar gasto<', page.data)
        settings = self.client.get('/settings')
        self.assertNotIn(b'name="sort_order"', settings.data)
        self.assertIn('Orden automático'.encode('utf-8'), settings.data)

    def test_close_declares_cash_and_mercadopago_as_one_total(self):
        token = self.login()
        self.open_cash(token)
        connection = sqlite3.connect(self.db_path)
        beverage_id = connection.execute("SELECT id FROM beverage_products WHERE beverage_type='Cerveza' ORDER BY id LIMIT 1").fetchone()[0]
        price = connection.execute("SELECT price FROM beverage_products WHERE id=?", (beverage_id,)).fetchone()[0]
        session_id = connection.execute("SELECT id FROM cash_sessions WHERE status='open'").fetchone()[0]
        connection.close()
        self.client.post('/movements/quick-sale', data={
            'sale_kind':'beverage','beverage_id':beverage_id,'quantity':'2',
            'payment_method':'mercadopago','csrf_token':token
        }, follow_redirects=True)
        expected_total = 10000 + price * 2
        response = self.client.post('/cash/close', data={
            'declared_cash': str(expected_total - 5000),
            'declared_mercadopago':'5000',
            'notes':'cierre prueba','csrf_token':token
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        connection = sqlite3.connect(self.db_path)
        row = connection.execute(
            'SELECT declared_cash,declared_mercadopago,declared_total,expected_total,difference FROM cash_sessions WHERE id=?',
            (session_id,),
        ).fetchone()
        connection.close()
        self.assertEqual(row[1], 5000)
        self.assertEqual(row[2], expected_total)
        self.assertEqual(row[3], expected_total)
        self.assertEqual(row[4], 0)

    def test_free_is_only_created_from_loaded_lists(self):
        token = self.login()
        self.open_cash(token)
        response = self.client.post('/movements/quick-sale', data={
            'sale_kind':'entry','category':'free','quantity':'1','payment_method':'other','csrf_token':token
        }, follow_redirects=True)
        self.assertIn(b'FREE se confirma desde Listas RRPP', response.data)
        connection = sqlite3.connect(self.db_path)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM movements WHERE category='free'").fetchone()[0], 0)
        common_id = connection.execute("SELECT id FROM promoters WHERE is_common=1").fetchone()[0]
        session_id = connection.execute("SELECT id FROM cash_sessions WHERE status='open'").fetchone()[0]
        admin_id = connection.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        guest_id = connection.execute(
            "INSERT INTO promoter_guests(cash_session_id,promoter_id,guest_name,normalized_name,source_filename,imported_at,imported_by) VALUES (?,?,?,?,?,?,?) RETURNING id",
            (session_id, common_id, 'Persona Free', 'persona free', 'bloc', app_module.now_iso(), admin_id),
        ).fetchone()[0]
        connection.commit(); connection.close()
        response = self.client.post(f'/promoter-lists/{guest_id}/check-in', data={'csrf_token':token}, follow_redirects=True)
        self.assertIn(b'Ingreso confirmado', response.data)
        connection = sqlite3.connect(self.db_path)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM movements WHERE category='free'").fetchone()[0], 1)
        connection.close()

    def test_beverage_variants_can_share_type_with_different_presentations_and_prices(self):
        token = self.login()
        first = self.client.post('/settings/beverages', data={
            'beverage_type':'Cerveza','brand_choice':'Quilmes','presentation':'lata 473 ml',
            'stock_unit':'lata','price':'5000','sort_order':'10','csrf_token':token
        }, follow_redirects=True)
        second = self.client.post('/settings/beverages', data={
            'beverage_type':'Cerveza','brand_choice':'Quilmes','presentation':'vaso',
            'stock_unit':'barril','price':'3000','sort_order':'11','csrf_token':token
        }, follow_redirects=True)
        self.assertIn(b'Variante agregada', first.data)
        self.assertIn(b'Variante agregada', second.data)
        connection = sqlite3.connect(self.db_path)
        rows = connection.execute("SELECT name,price,presentation FROM beverage_products WHERE beverage_type='Cerveza' AND brand='Quilmes' ORDER BY presentation").fetchall()
        connection.close()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row[1] for row in rows}, {3000,5000})

    def test_beverage_cashier_cannot_see_partial_sales_or_export(self):
        admin_token = self.login()
        self.open_cash(admin_token)
        self.client.post('/logout', data={'csrf_token':admin_token})
        token = self.login('bebidas','floki123')
        status = self.client.get('/api/status').get_json()
        self.assertNotIn('drink_count', status)
        self.assertEqual(self.client.get('/stock/export.xlsx').status_code, 403)
        page = self.client.get('/stock')
        self.assertIn(b'CONTEO CIEGO', page.data)
        self.assertNotIn(b'Total vendido', page.data)

    def test_admin_can_update_visible_user_names(self):
        token = self.login()
        connection = sqlite3.connect(self.db_path)
        admin_id = connection.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        beverages_id = connection.execute("SELECT id FROM users WHERE username='bebidas'").fetchone()[0]
        connection.close()
        response = self.client.post(
            f'/settings/users/{admin_id}/name',
            data={'name':'Pablo','csrf_token':token}, follow_redirects=True,
        )
        self.assertIn(b'Nombre visible actualizado', response.data)
        self.client.post(
            f'/settings/users/{beverages_id}/name',
            data={'name':'Lucas','csrf_token':token}, follow_redirects=True,
        )
        connection = sqlite3.connect(self.db_path)
        self.assertEqual(connection.execute("SELECT name FROM users WHERE id=?", (admin_id,)).fetchone()[0], 'Pablo')
        self.assertEqual(connection.execute("SELECT name FROM users WHERE id=?", (beverages_id,)).fetchone()[0], 'Lucas')
        connection.close()

    def test_price_rules_only_accept_thousand_multiples(self):
        self.assertEqual(app_module.price_from_option("8.000"), 8000)
        with self.assertRaises(ValueError):
            app_module.price_from_option("8500")
        row = {"cutoff_time": "03:30", "before_price": 8000, "after_price": 10000}
        self.assertEqual(app_module.resolve_entry_price(row, datetime(2026, 7, 30, 23, 0))[0], 8000)
        self.assertEqual(app_module.resolve_entry_price(row, datetime(2026, 7, 31, 4, 0))[0], 10000)


    def test_workspace_prediction_and_event_delete(self):
        token = self.login()
        self.open_cash(token)
        message = """[30/7/26, 12:43:26 p. m.] Pablo: CINTIA DÍAZ

Pilar tutti
Ingrid becerra
[30/7/26, 1:29:04 p. m.] Pablo: Persona Comun
"""
        response = self.client.post(
            "/promoter-lists/workspace/apply",
            data={"source_text": message, "import_mode": "sync", "csrf_token": token},
            follow_redirects=True,
        )
        self.assertIn(b"Listas convertidas", response.data)
        suggestions = self.client.get("/api/guest-suggestions?q=Pilar").get_json()["suggestions"]
        self.assertEqual(suggestions[0]["name"].lower(), "pilar tutti")
        self.assertEqual(suggestions[0]["lists"][0]["promoter_name"], "CINTIA DÍAZ")

        self.client.post(
            "/cash/close",
            data={"declared_cash": "10.000", "notes": "", "csrf_token": token},
            follow_redirects=True,
        )
        connection = sqlite3.connect(self.db_path)
        session_id = connection.execute("SELECT id FROM cash_sessions ORDER BY id DESC LIMIT 1").fetchone()[0]
        connection.close()
        response = self.client.post(
            f"/history/{session_id}/delete", data={"csrf_token": token}, follow_redirects=True
        )
        self.assertIn(b"eliminado del historial", response.data)
        connection = sqlite3.connect(self.db_path)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM cash_sessions WHERE id=?", (session_id,)).fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM movements WHERE cash_session_id=?", (session_id,)).fetchone()[0], 0)
        connection.close()

    def test_ticketing_and_beverage_sectors_are_enforced(self):
        admin_token = self.login()
        self.open_cash(admin_token)
        self.client.post("/logout", data={"csrf_token": admin_token})
        cashier_token = self.login("cajero", "floki123")
        connection = sqlite3.connect(self.db_path)
        beverage_id = connection.execute("SELECT id FROM beverage_products ORDER BY id LIMIT 1").fetchone()[0]
        connection.close()
        denied = self.client.post(
            "/movements/quick-sale",
            data={"sale_kind": "beverage", "beverage_id": beverage_id, "quantity": 1, "payment_method": "cash", "csrf_token": cashier_token},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.client.get("/history").status_code, 403)
        status = self.client.get("/api/status").get_json()
        self.assertNotIn("sales", status)
        self.assertEqual(status["sector"], "ticketing")

    def test_lists_can_be_exported_to_pdf_by_promoter(self):
        token = self.login()
        self.open_cash(token)
        connection = sqlite3.connect(self.db_path)
        session_id = connection.execute("SELECT id FROM cash_sessions WHERE status='open'").fetchone()[0]
        admin_id = connection.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        common_id = connection.execute("SELECT id FROM promoters WHERE is_common=1").fetchone()[0]
        connection.execute("INSERT INTO promoters(name,active,created_at,normalized_name,is_common,qr_token,qr_updated_at) VALUES (?,?,?,?,0,?,?)", ('PABLO',1,app_module.now_iso(),'pablo','token-pablo',app_module.now_iso()))
        promoter_id = connection.execute("SELECT id FROM promoters WHERE normalized_name='pablo'").fetchone()[0]
        for promoter, name, normalized in ((common_id,'Zoe Álvarez','zoe alvarez'),(promoter_id,'Ana Gómez','ana gomez')):
            connection.execute("INSERT INTO promoter_guests(cash_session_id,promoter_id,guest_name,normalized_name,source_filename,imported_at,imported_by) VALUES (?,?,?,?,?,?,?)", (session_id,promoter,name,normalized,'bloc',app_module.now_iso(),admin_id))
        connection.commit(); connection.close()

        grouped = self.client.get('/promoter-lists/export.pdf')
        self.assertEqual(grouped.status_code, 200)
        self.assertTrue(grouped.data.startswith(b'%PDF'))
        self.assertIn('por_promotor.pdf', grouped.headers['Content-Disposition'])

    def test_all_free_lists_expire_at_three_thirty(self):
        token = self.login()
        self.open_cash(token)
        connection = sqlite3.connect(self.db_path)
        session_id = connection.execute("SELECT id FROM cash_sessions WHERE status='open'").fetchone()[0]
        admin_id = connection.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
        common_id = connection.execute("SELECT id FROM promoters WHERE is_common=1").fetchone()[0]
        connection.execute("INSERT INTO promoters(name,active,created_at,normalized_name,is_common,qr_token,qr_updated_at) VALUES (?,?,?,?,0,?,?)", ('SOFÍA',1,app_module.now_iso(),'sofia','token-sofia',app_module.now_iso()))
        promoter_id = connection.execute("SELECT id FROM promoters WHERE normalized_name='sofia'").fetchone()[0]
        common_guest = connection.execute("INSERT INTO promoter_guests(cash_session_id,promoter_id,guest_name,normalized_name,source_filename,imported_at,imported_by) VALUES (?,?,?,?,?,?,?) RETURNING id", (session_id,common_id,'Común Test','comun test','bloc',app_module.now_iso(),admin_id)).fetchone()[0]
        promoter_guest = connection.execute("INSERT INTO promoter_guests(cash_session_id,promoter_id,guest_name,normalized_name,source_filename,imported_at,imported_by) VALUES (?,?,?,?,?,?,?) RETURNING id", (session_id,promoter_id,'Promotor Test','promotor test','bloc',app_module.now_iso(),admin_id)).fetchone()[0]
        connection.commit(); connection.close()

        with patch.object(app_module, 'free_entry_available', return_value=False):
            denied = self.client.post(f'/promoter-lists/{common_guest}/check-in', data={'csrf_token':token}, follow_redirects=True)
            promoter_denied = self.client.post(f'/promoter-lists/{promoter_guest}/check-in', data={'csrf_token':token}, follow_redirects=True)
        self.assertIn('finalizó a las 03:30'.encode('utf-8'), denied.data)
        self.assertIn('finalizó a las 03:30'.encode('utf-8'), promoter_denied.data)
        connection = sqlite3.connect(self.db_path)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM guest_checkins WHERE normalized_name='comun test'").fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM guest_checkins WHERE normalized_name='promotor test'").fetchone()[0], 0)
        connection.close()

    def test_event_image_is_saved_served_and_removed(self):
        token = self.login()
        png = b"\x89PNG\r\n\x1a\n" + b"test-image-data"
        response = self.client.post(
            "/cash/open",
            data={
                "opening_amount": "0",
                "event_name": "Noche Imagen",
                "event_date": "2026-08-05",
                "capacity": "",
                "event_image": (io.BytesIO(png), "historia.png"),
                "csrf_token": token,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Noche Imagen", response.data)
        connection = sqlite3.connect(self.db_path)
        session_id, image_name = connection.execute(
            "SELECT id,event_image_name FROM cash_sessions WHERE status='open'"
        ).fetchone()
        connection.close()
        self.assertEqual(image_name, "historia.png")
        banner = self.client.get(f"/events/{session_id}/banner")
        self.assertEqual(banner.status_code, 200)
        self.assertEqual(banner.mimetype, "image/png")
        self.assertTrue(banner.data.startswith(b"\x89PNG"))
        response = self.client.post(
            f"/events/{session_id}/banner",
            data={"banner_action": "remove", "csrf_token": token, "return_to": "/"},
            follow_redirects=True,
        )
        self.assertIn("banner Floki predeterminado".encode("utf-8"), response.data)
        connection = sqlite3.connect(self.db_path)
        values = connection.execute(
            "SELECT event_image_data,event_image_mime,event_image_name FROM cash_sessions WHERE id=?",
            (session_id,),
        ).fetchone()
        connection.close()
        self.assertEqual(values, (None, None, None))

    def test_cashier_permissions(self):
        token = self.login("cajero", "floki123")
        response = self.client.post(
            "/settings/users",
            data={"name": "Otro", "username": "otro", "password": "secreto1", "role": "cashier", "csrf_token": token},
        )
        self.assertEqual(response.status_code, 403)


class MigrationTestCase(unittest.TestCase):
    def test_v10_database_is_migrated_to_v21(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        connection = sqlite3.connect(db_path)
        connection.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,username TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
            CREATE TABLE cash_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT,opened_at TEXT NOT NULL,opened_by INTEGER NOT NULL,opening_amount REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'open',closed_at TEXT,closed_by INTEGER,declared_cash REAL,expected_cash REAL,difference REAL,notes TEXT);
            CREATE TABLE movements (id INTEGER PRIMARY KEY AUTOINCREMENT,cash_session_id INTEGER NOT NULL,movement_type TEXT NOT NULL,category TEXT NOT NULL,description TEXT,quantity INTEGER NOT NULL DEFAULT 1,unit_price REAL NOT NULL,total REAL NOT NULL,payment_method TEXT NOT NULL,created_at TEXT NOT NULL,created_by INTEGER NOT NULL,voided INTEGER NOT NULL DEFAULT 0,voided_at TEXT,voided_by INTEGER,void_reason TEXT);
            """
        )
        connection.commit()
        connection.close()

        original_db = app_module.app.config["DATABASE"]
        app_module.app.config["DATABASE"] = db_path
        try:
            app_module.init_db()
            connection = sqlite3.connect(db_path)
            cash_columns = {row[1] for row in connection.execute("PRAGMA table_info(cash_sessions)")}
            movement_columns = {row[1] for row in connection.execute("PRAGMA table_info(movements)")}
            self.assertTrue({"event_name", "event_date", "capacity", "event_image_data", "event_image_mime", "event_image_name"}.issubset(cash_columns))
            self.assertIn("promoter_id", movement_columns)
            self.assertIn("beverage_product_id", movement_columns)
            self.assertIn("stock_units", movement_columns)
            beverage_columns = {row[1] for row in connection.execute("PRAGMA table_info(beverage_products)")}
            self.assertTrue({"stock_unit", "sale_unit", "servings_per_stock_unit", "beverage_type", "brand", "presentation"}.issubset(beverage_columns))
            user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
            self.assertIn("sector", user_columns)
            for table in ("entry_prices", "beverage_products", "ticketing_products", "beverage_stock", "promoter_guests", "guest_checkins", "list_imports", "list_workspaces"):
                self.assertIsNotNone(connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM entry_prices").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT category FROM entry_prices WHERE active=1").fetchone()[0], "general")
            common = connection.execute("SELECT is_common, qr_token FROM promoters WHERE name='LISTA COMÚN'").fetchone()
            self.assertEqual(common[0], 1)
            self.assertIsNone(common[1])
            connection.close()
        finally:
            app_module.app.config["DATABASE"] = original_db
            Path(db_path).unlink(missing_ok=True)

    def test_champagne_and_energizer_are_independent_products(self):
        token = self.login()
        self.open_cash(token)
        self.client.post('/settings/beverages', data={
            'beverage_type':'Energizante','brand_choice':'Speed','presentation':'lata 250 ml',
            'price':'3000','stock_unit':'lata','sort_order':'31','csrf_token':token
        }, follow_redirects=True)
        self.client.post('/settings/beverages', data={
            'beverage_type':'Espumante','brand_choice':'Chandon','presentation':'botella 750 ml',
            'price':'20500','stock_unit':'botella','sort_order':'80','csrf_token':token
        }, follow_redirects=True)

        connection = sqlite3.connect(self.db_path)
        champagne_id = connection.execute("SELECT id FROM beverage_products WHERE active=1 AND brand='Chandon'").fetchone()[0]
        speed_id = connection.execute("SELECT id FROM beverage_products WHERE active=1 AND brand='Speed'").fetchone()[0]
        connection.close()

        response = self.client.post('/movements/quick-sale', data={
            'sale_kind':'beverage','beverage_id':champagne_id,'quantity':'2',
            'payment_method':'cash','csrf_token':token
        }, follow_redirects=True)
        self.assertIn(b'Venta r', response.data)
        self.assertNotIn(b'Speed (2 por champagne)', response.data)

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        main = connection.execute("SELECT * FROM movements WHERE beverage_product_id=? AND category='drink' ORDER BY id DESC LIMIT 1", (champagne_id,)).fetchone()
        self.assertEqual(main['quantity'], 2)
        self.assertEqual(main['total'], 41000)
        # Champagne no debe crear ni movimientos ni ajustes automáticos de Energizante.
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM beverage_stock_adjustments WHERE parent_movement_id=? AND reason='champagne_speed'", (main['id'],)).fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM movements WHERE category='champagne_speed' AND cash_session_id=?", (main['cash_session_id'],)).fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM movements WHERE beverage_product_id=? AND cash_session_id=?", (speed_id, main['cash_session_id'])).fetchone()[0], 0)
        connection.close()

        # El energizante se registra como una venta independiente cuando el operador lo toca.
        self.client.post('/movements/quick-sale', data={
            'sale_kind':'beverage','beverage_id':speed_id,'quantity':'2',
            'payment_method':'cash','csrf_token':token
        }, follow_redirects=True)
        connection = sqlite3.connect(self.db_path)
        speed_sale = connection.execute("SELECT quantity, total FROM movements WHERE beverage_product_id=? AND category='drink' ORDER BY id DESC LIMIT 1", (speed_id,)).fetchone()
        connection.close()
        self.assertEqual(speed_sale[0], 2)
        self.assertEqual(speed_sale[1], 6000)

    def test_beverage_cashier_can_open_full_beverage_history_but_ticketing_cannot(self):
        admin_token = self.login()
        self.open_cash(admin_token)
        connection = sqlite3.connect(self.db_path)
        beverage_id = connection.execute("SELECT id FROM beverage_products WHERE active=1 ORDER BY id LIMIT 1").fetchone()[0]
        connection.close()
        self.client.post('/movements/quick-sale', data={
            'sale_kind':'beverage','beverage_id':beverage_id,'quantity':'1','payment_method':'cash','csrf_token':admin_token
        }, follow_redirects=True)
        self.client.post('/logout', data={'csrf_token':admin_token})

        beverage_token = self.login('bebidas','floki123')
        page = self.client.get('/beverages/history')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Historial de ventas de bebidas', page.data)
        self.assertIn(b'movimientos', page.data)
        self.client.post('/logout', data={'csrf_token':beverage_token})

        self.login('cajero','floki123')
        self.assertEqual(self.client.get('/beverages/history').status_code, 403)

    def test_champagne_and_energizers_stay_adjacent_in_quick_sale_groups(self):
        rows = [
            {"id": 1, "name": "Cerveza Quilmes · Lata", "beverage_type": "Cerveza", "brand": "Quilmes", "sale_unit": "lata"},
            {"id": 2, "name": "Espumante Chandon · Botella", "beverage_type": "Espumante", "brand": "Chandon", "sale_unit": "botella"},
            {"id": 3, "name": "Energizante Speed · Lata", "beverage_type": "Energizante", "brand": "Speed", "sale_unit": "lata"},
            {"id": 4, "name": "Vodka Skyy · Vaso", "beverage_type": "Vodka", "brand": "Skyy", "sale_unit": "vaso"},
        ]
        groups = app_module.group_beverages(
            rows,
            product_ranking={1: 100, 4: 90, 3: 80, 2: 10},
            category_ranking={"CERVEZAS": 100, "VODKA": 90, "ENERGIZANTES": 80, "CHAMPAGNE": 10},
        )
        labels = [group["label"] for group in groups]
        champagne_index = labels.index("CHAMPAGNE")
        self.assertEqual(labels[champagne_index + 1], "ENERGIZANTES")
        self.assertEqual(app_module.infer_beverage_category("Energizante", "Speed", "lata", "Speed"), "ENERGIZANTES")



if __name__ == "__main__":
    unittest.main()
