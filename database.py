import sqlite3
import os
import hashlib

DB_FILE = os.path.join(os.path.dirname(__file__), 'angkor_thom_edu.db')

def generate_password_hash(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def check_password_hash(pwd_hash, password):
    return pwd_hash == hashlib.sha256(password.encode('utf-8')).hexdigest()

class DictRow(dict):
    def __getitem__(self, item):
        if isinstance(item, int):
            return list(self.values())[item]
        return super().__getitem__(item)

def dict_factory(cursor, row):
    return DictRow((col[0], row[idx]) for idx, col in enumerate(cursor.description))

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = dict_factory
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Schools Table
    school_sql = cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='schools'").fetchone()
    if school_sql and school_sql.get('sql') and 'community_preschool' not in school_sql.get('sql'):
        cursor.execute("DROP TABLE IF EXISTS schools")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name_kh TEXT NOT NULL,
            name_en TEXT,
            level TEXT CHECK(level IN ('community_preschool', 'state_preschool', 'preschool', 'primary', 'secondary', 'high')) NOT NULL,
            commune TEXT NOT NULL,
            village TEXT NOT NULL,
            principal_name TEXT NOT NULL,
            principal_phone TEXT,
            classrooms INTEGER DEFAULT 0,
            buildings INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Users Table
    user_sql = cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    if user_sql and user_sql.get('sql') and 'other' not in user_sql.get('sql'):
        cursor.execute("CREATE TABLE users_old_tmp AS SELECT * FROM users")
        cursor.execute("DROP TABLE users")
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT CHECK(role IN ('admin', 'user', 'other')) NOT NULL,
                school_id INTEGER,
                position TEXT,
                phone TEXT,
                FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL
            )
        ''')
        cursor.execute("INSERT INTO users (id, username, password_hash, full_name, role, school_id, position, phone) SELECT id, username, password_hash, full_name, role, school_id, position, phone FROM users_old_tmp")
        cursor.execute("DROP TABLE users_old_tmp")
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT CHECK(role IN ('admin', 'user', 'other')) NOT NULL,
                school_id INTEGER,
                position TEXT,
                phone TEXT,
                FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL
            )
        ''')

    # 3. Staff / Teacher Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id_num TEXT UNIQUE NOT NULL,
            name_kh TEXT NOT NULL,
            name_en TEXT NOT NULL,
            sex TEXT CHECK(sex IN ('M', 'F')) NOT NULL,
            dob TEXT,
            phone TEXT,
            email TEXT,
            school_id INTEGER NOT NULL,
            framework TEXT CHECK(framework IN ('A', 'B', 'C')) NOT NULL,
            position TEXT NOT NULL,
            subject_specialty TEXT NOT NULL,
            current_grade TEXT,
            salary_index REAL DEFAULT 1.0,
            status TEXT CHECK(status IN ('active', 'transferred', 'retired')) DEFAULT 'active',
            photo_url TEXT,
            FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
        )
    ''')

    # 4. Staff History Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            change_type TEXT CHECK(change_type IN ('transfer', 'promotion', 'salary_step')) NOT NULL,
            effective_date TEXT NOT NULL,
            old_detail TEXT,
            new_detail TEXT,
            reference_doc TEXT,
            notes TEXT,
            FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE
        )
    ''')

    # 5. Staff Leaves Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff_leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            type TEXT CHECK(type IN ('leave', 'training')) NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            title TEXT NOT NULL,
            location_or_reason TEXT,
            status TEXT CHECK(status IN ('pending', 'approved', 'rejected')) DEFAULT 'approved',
            FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE
        )
    ''')

    # 6. Student Statistics Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            total_students INTEGER NOT NULL DEFAULT 0,
            female_students INTEGER NOT NULL DEFAULT 0,
            disabled_students INTEGER NOT NULL DEFAULT 0,
            disabled_female INTEGER NOT NULL DEFAULT 0,
            scholarship_students INTEGER NOT NULL DEFAULT 0,
            scholarship_female INTEGER NOT NULL DEFAULT 0,
            dropout_count INTEGER NOT NULL DEFAULT 0,
            dropout_female INTEGER NOT NULL DEFAULT 0,
            repetition_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
        )
    ''')

    # 7. Exam Results Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            exam_type TEXT CHECK(exam_type IN ('diploma_grade_9', 'bacii_grade_12')) NOT NULL,
            total_candidates INTEGER NOT NULL DEFAULT 0,
            female_candidates INTEGER NOT NULL DEFAULT 0,
            total_passed INTEGER NOT NULL DEFAULT 0,
            female_passed INTEGER NOT NULL DEFAULT 0,
            grade_a INTEGER DEFAULT 0,
            grade_b INTEGER DEFAULT 0,
            grade_c INTEGER DEFAULT 0,
            grade_d INTEGER DEFAULT 0,
            grade_e INTEGER DEFAULT 0,
            FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
        )
    ''')

    # 8. Sports Events Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sports_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT CHECK(category IN ('primary', 'secondary')) NOT NULL,
            academic_year TEXT NOT NULL,
            event_date TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT CHECK(status IN ('upcoming', 'completed')) DEFAULT 'upcoming'
        )
    ''')

    # 9. Sports Athletes Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sports_athletes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            school_id INTEGER NOT NULL,
            athlete_name TEXT NOT NULL,
            sex TEXT CHECK(sex IN ('M', 'F')) NOT NULL,
            sport_type TEXT NOT NULL,
            achievement TEXT,
            FOREIGN KEY (event_id) REFERENCES sports_events(id) ON DELETE CASCADE,
            FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
        )
    ''')

    # 10. Youth Clubs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS youth_clubs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            club_type TEXT CHECK(club_type IN ('youth_club', 'scout', 'volunteer')) NOT NULL,
            location TEXT NOT NULL,
            leader_name TEXT NOT NULL,
            total_members INTEGER DEFAULT 0,
            female_members INTEGER DEFAULT 0,
            activity_date TEXT,
            description TEXT
        )
    ''')

    # 11. Documents Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_number TEXT NOT NULL,
            doc_type TEXT CHECK(doc_type IN ('inbound', 'outbound')) NOT NULL,
            title TEXT NOT NULL,
            source_destination TEXT NOT NULL,
            doc_date TEXT NOT NULL,
            scanned_file TEXT,
            category TEXT DEFAULT 'លិខិតផ្លូវការ',
            status TEXT DEFAULT 'កត់ត្រារួច'
        )
    ''')

    # 12. Mission Orders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mission_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            officer_names TEXT NOT NULL,
            destination_schools TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            purpose TEXT NOT NULL,
            approved_by TEXT DEFAULT 'ប្រធានការិយាល័យ',
            status TEXT CHECK(status IN ('pending', 'approved', 'completed')) DEFAULT 'approved',
            allowance_amount REAL DEFAULT 40000.0,
            remarks TEXT
        )
    ''')

    # Migration check for existing databases
    try:
        cursor.execute("ALTER TABLE mission_orders ADD COLUMN allowance_amount REAL DEFAULT 40000.0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE mission_orders ADD COLUMN remarks TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE mission_orders ADD COLUMN ref_doc TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE mission_orders ADD COLUMN lunar_date_str TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE staff ADD COLUMN bank_account TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE student_stats ADD COLUMN disabled_female INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE student_stats ADD COLUMN scholarship_female INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE student_stats ADD COLUMN dropout_female INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Office Staff Table (Module 2.2: District Office Staff)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS office_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id_num TEXT UNIQUE NOT NULL,
            name_kh TEXT NOT NULL,
            name_en TEXT NOT NULL,
            sex TEXT CHECK(sex IN ('M', 'F')) NOT NULL,
            dob TEXT,
            phone TEXT,
            email TEXT,
            office_unit TEXT NOT NULL,
            framework TEXT CHECK(framework IN ('A', 'B', 'C')) NOT NULL,
            position TEXT NOT NULL,
            current_grade TEXT,
            salary_index REAL DEFAULT 1.0,
            status TEXT CHECK(status IN ('active', 'transferred', 'retired')) DEFAULT 'active',
            photo_url TEXT,
            bank_account TEXT
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM office_staff")
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO office_staff (staff_id_num, name_kh, name_en, sex, dob, phone, email, office_unit, framework, position, current_grade, salary_index, bank_account, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            ('OFF-001', 'លោក រ៉ាត់ សំអឿន', 'Rat Samoeun', 'M', '1975-05-10', '012 333 444', 'samoeun@edu.gov.kh', 'ថ្នាក់ដឹកនាំការិយាល័យ', 'A', 'ប្រធានការិយាល័យ', 'ក.១.១', 4.2, '012345678', 'active'),
            ('OFF-002', 'លោកស្រី សុខ ចាន់ណា', 'Sok Channa', 'F', '1980-09-15', '017 666 777', 'channa@edu.gov.kh', 'ថ្នាក់ដឹកនាំការិយាល័យ', 'A', 'អនុប្រធានការិយាល័យ', 'ក.១.២', 3.8, '098765432', 'active'),
            ('OFF-003', 'លោក អ៊ឹម សុធា', 'Im Sothea', 'M', '1986-12-04', '012 111 222', 'sothea@edu.gov.kh', 'ផ្នែកព័ត៌មានវិទ្យា និងស្ថិតិ', 'A', 'មន្ត្រីព័ត៌មានវិទ្យា', 'ក.១.៤', 3.2, '112233445', 'active'),
            ('OFF-004', 'លោកស្រី គិម ផាន់', 'Kim Phan', 'F', '1983-03-22', '092 888 777', 'phan@edu.gov.kh', 'ផ្នែកបឋមសិក្សា', 'B', 'ប្រធានផ្នែកបឋមសិក្សា', 'ខ.១.១', 3.0, '554433221', 'active'),
            ('OFF-005', 'លោក ជា តិចស៊ីន', 'Chea Techsin', 'M', '1989-07-19', '015 999 000', 'techsin@edu.gov.kh', 'ផ្នែកយុវជន និងកីឡា', 'B', 'ប្រធានផ្នែកយុវជន និងកីឡា', 'ខ.១.៣', 2.8, '667788990', 'active'),
        ])

    # 13. Assets Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_id INTEGER NOT NULL,
            asset_name TEXT NOT NULL,
            category TEXT CHECK(category IN ('furniture', 'computer', 'textbook', 'equipment')) NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            condition TEXT CHECK(condition IN ('good', 'repair_needed', 'broken')) DEFAULT 'good',
            date_allocated TEXT,
            FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
        )
    ''')

    # 14. Budgets Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            budget_type TEXT CHECK(budget_type IN ('PB_operational', 'school_development', 'grant')) NOT NULL,
            allocated_amount REAL NOT NULL DEFAULT 0.0,
            spent_amount REAL NOT NULL DEFAULT 0.0,
            notes TEXT,
            FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE
        )
    ''')

    # 15. Audit Logs Table (Module 9: Activity Logging)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            user_name TEXT NOT NULL,
            action_type TEXT CHECK(action_type IN ('CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT')) NOT NULL,
            module TEXT NOT NULL,
            details TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    try:
        cursor.execute("UPDATE users SET role = 'user' WHERE role NOT IN ('admin', 'user')")
    except Exception:
        pass

    conn.commit()
    conn.close()

def log_activity(conn_or_none, user_id, username, user_name, action_type, module, details):
    should_close = False
    if conn_or_none is None:
        conn = get_db_connection()
        should_close = True
    else:
        conn = conn_or_none
    try:
        conn.execute('''
            INSERT INTO audit_logs (user_id, username, user_name, action_type, module, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username or 'system', user_name or 'ប្រព័ន្ធ', action_type, module, details))
        if should_close:
            conn.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")
    finally:
        if should_close:
            conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
