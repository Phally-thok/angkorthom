import sqlite3
from database import init_db, get_db_connection, generate_password_hash

def seed_database():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear existing data safely
    tables = [
        'users', 'schools', 'staff', 'staff_history', 'staff_leaves',
        'student_stats', 'exam_results', 'sports_events', 'sports_athletes',
        'youth_clubs', 'documents', 'mission_orders', 'assets', 'budgets'
    ]
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")

    # Reset sqlite sequence
    cursor.execute("DELETE FROM sqlite_sequence")

    print("Seeding Schools in Angkor Thom District...")
    schools_data = [
        ('SCH-AT001', 'វិទ្យាល័យ ហ៊ុន សែន អង្គរធំ', 'Hun Sen Angkor Thom High School', 'high', 'លាងដៃ', 'លាងដៃ', 'លោក សោម វណ្ណា', '012 345 678', 24, 4),
        ('SCH-AT002', 'អនុវិទ្យាល័យ ពាក់ស្នែង', 'Peak Snaeng Secondary School', 'secondary', 'ពាក់ស្នែង', 'ពាក់ស្នែង', 'លោកស្រី ចាន់ ធារី', '097 888 9911', 12, 2),
        ('SCH-AT003', 'អនុវិទ្យាល័យ ជប់តារ៉ាវ', 'Chup Ta Trav Secondary School', 'secondary', 'ជប់តារ៉ាវ', 'ជប់', 'លោក គឹម សុផល', '017 555 432', 10, 2),
        ('SCH-AT004', 'សាលាបឋមសិក្សា លាងដៃ', 'Leang Dai Primary School', 'primary', 'លាងដៃ', 'លាងដៃ', 'លោកស្រី ម៉េង សុខា', '088 222 3344', 16, 3),
        ('SCH-AT005', 'សាលាបឋមសិក្សា ពាក់ស្នែង', 'Peak Snaeng Primary School', 'primary', 'ពាក់ស្នែង', 'ពាក់ស្នែង', 'លោក អ៊ុក សារិន', '012 999 111', 14, 2),
        ('SCH-AT006', 'សាលាបឋមសិក្សា ស្វាយចេក', 'Svay Chek Primary School', 'primary', 'ស្វាយចេក', 'ស្វាយចេក', 'លោក ហែម ពិសិដ្ឋ', '092 333 444', 10, 2),
        ('SCH-AT007', 'សាលាបឋមសិក្សា ត្រពាំងស្វាយ', 'Trapeang Svay Primary School', 'primary', 'ជប់តារ៉ាវ', 'ត្រពាំងស្វាយ', 'លោកស្រី គង់ ស្រីមុំ', '011 777 888', 8, 1),
        ('SCH-AT000A', 'សាលាមត្តេយ្យសិក្សារដ្ឋ លាងដៃ', 'Leang Dai State Preschool', 'state_preschool', 'លាងដៃ', 'លាងដៃ', 'លោកស្រី ឡុង សុភា', '012 888 777', 6, 1),
        ('SCH-AT000B', 'សាលាមត្តេយ្យសិក្សាសហគមន៍ ពាក់ស្នែង', 'Peak Snaeng Community Preschool', 'community_preschool', 'ពាក់ស្នែង', 'ពាក់ស្នែង', 'លោកស្រី ស៊ុម វណ្ណនី', '097 555 1122', 4, 1),
    ]

    cursor.executemany('''
        INSERT INTO schools (code, name_kh, name_en, level, commune, village, principal_name, principal_phone, classrooms, buildings)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', schools_data)

    # 2. Users (Admin, Chief, School Representatives)
    print("Seeding Users...")
    users_data = [
        ('admin', generate_password_hash('admin123'), 'លោក អ៊ឹម សុធា', 'admin', None, 'មន្ត្រីព័ត៌មានវិទ្យា', '012 111 222'),
        ('chief', generate_password_hash('chief123'), 'លោក រ៉ាត់ សំអឿន', 'user', None, 'ប្រធានការិយាល័យ', '012 333 444'),
        ('deputy', generate_password_hash('deputy123'), 'លោកស្រី សុខ ចាន់ណា', 'user', None, 'អនុប្រធានការិយាល័យ', '017 666 777'),
        ('principal_at', generate_password_hash('school123'), 'លោក សោម វណ្ណា', 'user', 1, 'នាយកវិទ្យាល័យ ហ៊ុន សែន អង្គរធំ', '012 345 678'),
        ('principal_ps', generate_password_hash('school123'), 'លោកស្រី ចាន់ ធារី', 'user', 2, 'នាយិកាអនុវិទ្យាល័យ ពាក់ស្នែង', '097 888 9911'),
    ]

    cursor.executemany('''
        INSERT INTO users (username, password_hash, full_name, role, school_id, position, phone)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', users_data)

    # 3. Staff & Teachers (Digital Profiles)
    print("Seeding Teachers & Staff...")
    staff_data = [
        ('T-00101', 'លោក សោម វណ្ណា', 'Som Vanna', 'M', '1978-04-12', '012 345 678', 'vanna@edu.gov.kh', 1, 'A', 'នាយកសាលា', 'គ្រប់គ្រងអប់រំ', 'ក.១.៣', 3.5),
        ('T-00102', 'លោកស្រី គង់ សុភានី', 'Kong Sophany', 'F', '1985-08-20', '092 111 333', 'sophany@edu.gov.kh', 1, 'A', 'គ្រូបង្រៀនកម្រិតឧត្តម', 'អក្សរសាស្ត្រខ្មែរ', 'ក.១.៤', 3.2),
        ('T-00103', 'លោក ចាន់ វីរៈ', 'Chan Virak', 'M', '1988-11-05', '017 222 444', 'virak@edu.gov.kh', 1, 'B', 'គ្រូបង្រៀនកម្រិតមូលដ្ឋាន', 'គណិតវិទ្យា', 'ខ.២.១', 2.8),
        ('T-00104', 'លោកស្រី នួន ចាន់ថា', 'Nuon Chantha', 'F', '1990-02-14', '088 333 555', 'chantha@edu.gov.kh', 1, 'B', 'គ្រូបង្រៀនកម្រិតមូលដ្ឋាន', 'រូបវិទ្យា', 'ខ.២.២', 2.6),
        ('T-00201', 'លោកស្រី ចាន់ ធារី', 'Chan Theary', 'F', '1982-06-18', '097 888 9911', 'theary@edu.gov.kh', 2, 'A', 'នាយិកាសាលា', 'គ្រប់គ្រងអប់រំ', 'ក.១.៤', 3.3),
        ('T-00202', 'លោក ផាន់ សុជាតិ', 'Phan Socheat', 'M', '1992-01-25', '011 444 666', 'socheat@edu.gov.kh', 2, 'B', 'គ្រូបង្រៀនកម្រិតមូលដ្ឋាន', 'ភាសាអង់គ្លេស', 'ខ.២.៣', 2.4),
        ('T-00301', 'លោក គឹម សុផល', 'Kim Sophal', 'M', '1980-09-30', '017 555 432', 'sophal@edu.gov.kh', 3, 'A', 'នាយកសាលា', 'គ្រប់គ្រងអប់រំ', 'ក.១.៣', 3.4),
        ('T-00401', 'លោកស្រី ម៉េង សុខា', 'Meng Sokha', 'F', '1984-03-15', '088 222 3344', 'sokha@edu.gov.kh', 4, 'B', 'នាយិកាសាលា', 'អប់រំបឋមសិក្សា', 'ខ.១.២', 3.0),
        ('T-00402', 'លោក ហ៊ិន រតនា', 'Hin Rattana', 'M', '1994-07-22', '093 555 777', 'rattana@edu.gov.kh', 4, 'C', 'គ្រូបង្រៀនបឋមសិក្សា', 'បឋមសិក្សា', 'គ.១.១', 2.0),
        ('T-00501', 'លោក អ៊ុក សារិន', 'Ouk Sarin', 'M', '1983-12-10', '012 999 111', 'sarin@edu.gov.kh', 5, 'B', 'នាយកសាលា', 'អប់រំបឋមសិក្សា', 'ខ.១.៣', 2.9),
    ]

    cursor.executemany('''
        INSERT INTO staff (staff_id_num, name_kh, name_en, sex, dob, phone, email, school_id, framework, position, subject_specialty, current_grade, salary_index)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', staff_data)

    # 4. Staff History & Promotions
    history_data = [
        (1, 'promotion', '2025-01-10', 'ថ្នាក់ ក.១.៤', 'ថ្នាក់ ក.១.៣', 'ប្រកាសលេខ ៤៥ អយក', 'ដំឡើងថ្នាក់មន្ត្រីរាជការ'),
        (2, 'salary_step', '2024-06-01', 'កាំប្រាក់ ៣.០', 'កាំប្រាក់ ៣.២', 'អនុក្រឹត្យលេខ ៧៨៩', 'ដំឡើងកាំប្រាក់ប្រចាំឆ្នាំ'),
        (6, 'transfer', '2024-09-01', 'អនុវិទ្យាល័យ ជប់តារ៉ាវ', 'អនុវិទ្យាល័យ ពាក់ស្នែង', 'លិខិតផ្ទេរលេខ ១២៣', 'ផ្ទេរតាមសំណើផ្ទាល់ខ្លួន'),
    ]
    cursor.executemany('''
        INSERT INTO staff_history (staff_id, change_type, effective_date, old_detail, new_detail, reference_doc, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', history_data)

    # 5. Staff Leaves & Training
    leaves_data = [
        (2, 'training', '2026-03-01', '2026-03-05', 'វគ្គបណ្តុះបណ្តាលវិធីសាស្ត្របង្រៀនឌីជីថល', 'មន្ទីរអប់រំខេត្តសៀមរាប', 'approved'),
        (4, 'leave', '2026-05-10', '2026-05-12', 'សុំច្បាប់ព្យាបាលជំងឺ', 'ស្រុកអង្គរធំ', 'approved'),
        (9, 'training', '2026-04-15', '2026-04-17', 'វគ្គអប់រំកាយរឹទ្ធិជាតិ', 'សាលាខេត្តសៀមរាប', 'approved'),
    ]
    cursor.executemany('''
        INSERT INTO staff_leaves (staff_id, type, start_date, end_date, title, location_or_reason, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', leaves_data)

    # 6. Student Statistics (Multi-Year Data for 5 Education Levels)
    student_stats_data = [
        # --- 2023-2024 ---
        (1, '2023-2024', 790, 400, 10, 4, 40, 20, 22, 15), # High
        (2, '2023-2024', 390, 195, 5, 2, 22, 10, 12, 8),   # Secondary
        (3, '2023-2024', 350, 175, 3, 1, 18, 9, 11, 6),    # Secondary
        (4, '2023-2024', 480, 240, 7, 3, 30, 15, 15, 10),  # Primary
        (5, '2023-2024', 430, 215, 4, 2, 25, 12, 10, 8),   # Primary
        (6, '2023-2024', 290, 145, 2, 1, 12, 6, 8, 5),    # Primary
        (7, '2023-2024', 220, 110, 2, 1, 8, 4, 6, 4),     # Primary
        (8, '2023-2024', 110, 55, 1, 0, 6, 3, 2, 1),      # State Preschool
        (9, '2023-2024', 70, 40, 0, 0, 4, 2, 2, 1),       # Community Preschool

        # --- 2024-2025 ---
        (1, '2024-2025', 820, 420, 11, 4, 42, 21, 20, 14), # High
        (2, '2024-2025', 405, 205, 5, 2, 24, 11, 10, 7),   # Secondary
        (3, '2024-2025', 365, 185, 4, 1, 19, 9, 9, 5),    # Secondary
        (4, '2024-2025', 500, 255, 7, 3, 32, 16, 13, 9),   # Primary
        (5, '2024-2025', 445, 222, 5, 2, 28, 14, 9, 7),    # Primary
        (6, '2024-2025', 300, 150, 3, 1, 14, 7, 7, 4),    # Primary
        (7, '2024-2025', 235, 118, 2, 1, 9, 4, 5, 3),     # Primary
        (8, '2024-2025', 125, 65, 1, 0, 7, 3, 2, 1),      # State Preschool
        (9, '2024-2025', 85, 45, 1, 1, 5, 3, 1, 0),       # Community Preschool

        # --- 2025-2026 ---
        (1, '2025-2026', 850, 440, 12, 5, 45, 22, 18, 12), # High
        (2, '2025-2026', 420, 215, 6, 2, 25, 12, 8, 6),    # Secondary
        (3, '2025-2026', 380, 190, 4, 1, 20, 10, 10, 5),   # Secondary
        (4, '2025-2026', 520, 270, 8, 3, 35, 18, 12, 9),   # Primary
        (5, '2025-2026', 460, 230, 5, 2, 30, 15, 9, 7),    # Primary
        (6, '2025-2026', 310, 155, 3, 1, 15, 8, 6, 4),    # Primary
        (7, '2025-2026', 240, 120, 2, 1, 10, 5, 5, 3),     # Primary
        (8, '2025-2026', 140, 75, 2, 1, 8, 4, 1, 0),      # State Preschool
        (9, '2025-2026', 95, 50, 1, 0, 7, 4, 1, 1),       # Community Preschool
    ]
    cursor.executemany('''
        INSERT INTO student_stats (school_id, academic_year, total_students, female_students, disabled_students, disabled_female, scholarship_students, scholarship_female, dropout_count, repetition_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', student_stats_data)

    # 7. Exam Results
    exam_results_data = [
        (1, '2024-2025', 'bacii_grade_12', 180, 95, 152, 84, 5, 18, 42, 50, 37),
        (1, '2024-2025', 'diploma_grade_9', 140, 72, 133, 70, 12, 30, 45, 35, 11),
        (2, '2024-2025', 'diploma_grade_9', 95, 50, 88, 48, 6, 18, 30, 24, 10),
        (3, '2024-2025', 'diploma_grade_9', 85, 43, 78, 41, 4, 15, 28, 22, 9),
    ]
    cursor.executemany('''
        INSERT INTO exam_results (school_id, academic_year, exam_type, total_candidates, female_candidates, total_passed, female_passed, grade_a, grade_b, grade_c, grade_d, grade_e)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', exam_results_data)

    # 8. Sports Events & Athletes
    cursor.execute('''
        INSERT INTO sports_events (title, category, academic_year, event_date, location, status)
        VALUES ('ការប្រកួតកីឡាសិស្សបឋម/មធ្យមសិក្សាជ្រើសរើសជើងឯកស្រុកអង្គរធំ', 'secondary', '2025-2026', '2026-02-20', 'ទីលានវិទ្យាល័យ ហ៊ុន សែន អង្គរធំ', 'completed')
    ''')
    event_id = cursor.lastrowid

    athletes_data = [
        (event_id, 1, 'កញ្ញា សុខ លីណា', 'F', 'រត់ប្រណាំង ១០០ម៉ែត្រ', 'មេដាយមាស'),
        (event_id, 2, 'យុវជន គង់ វិចិត្រ', 'M', 'បាល់ទាត់', 'មេដាយប្រាក់'),
        (event_id, 3, 'កញ្ញា ម៉េង ស្រីណុច', 'F', 'បាល់ទះ', 'មេដាយសំរិទ្ធ'),
    ]
    cursor.executemany('''
        INSERT INTO sports_athletes (event_id, school_id, athlete_name, sex, sport_type, achievement)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', athletes_data)

    # 9. Youth Clubs & Scouts
    youth_clubs_data = [
        ('ក្លឹបយុវជនកាយរឹទ្ធិជាតិ ស្រុកអង្គរធំ', 'scout', 'វិទ្យាល័យ ហ៊ុន សែន អង្គរធំ', 'លោក សោម វណ្ណា', 65, 32, '2026-01-15', 'សកម្មភាពបោះជំរុំ និងការងារស្ម័គ្រចិត្តសម្អាតបរិស្ថានក្បែរប្រាសាទ'),
        ('ក្លឹបយុវជនស្ម័គ្រចិត្តអភិវឌ្ឍន៍សហគមន៍', 'volunteer', 'ឃុំលាងដៃ', 'កញ្ញា ឈិន សុភា', 40, 22, '2026-02-10', 'សកម្មភាពចុះជួយបង្រៀនសិស្សក្រីក្រ និងយុទ្ធនាការអានសៀវភៅ'),
    ]
    cursor.executemany('''
        INSERT INTO youth_clubs (title, club_type, location, leader_name, total_members, female_members, activity_date, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', youth_clubs_data)

    # 10. Documents
    docs_data = [
        ('១៥២/២៦ អយក.សរ', 'inbound', 'ណែនាំស្តីពីការរៀបចំការប្រឡងឆមាសទី១', 'មន្ទីរអប់រំ យុវជន និងកីឡា ខេត្តសៀមរាប', '2026-02-01', 'doc_152_2026.pdf', 'លិខិតណែនាំ', 'កត់ត្រារួច'),
        ('០៨៩/២៦ អយក.អធ', 'outbound', 'របាយការណ៍ស្ថិតិសិស្ស និងបុគ្គលិកអប់រំដើមឆ្នាំសិក្សា ២០២៥-២០២៦', 'មន្ទីរអប់រំ យុវជន និងកីឡា ខេត្តសៀមរាប', '2026-02-10', 'doc_089_2026.pdf', 'របាយការណ៍', 'ផ្ញើរួច'),
        ('០៤៥/២៦ អយក.អធ', 'outbound', 'លិខិតអញ្ជើញនាយកសាលាចូលរួមប្រជុំបូកសរុបការងារប្រចាំខែ', 'គ្រប់សាលារៀនក្នុងស្រុកអង្គរធំ', '2026-02-14', 'doc_045_2026.pdf', 'លិខិតអញ្ជើញ', 'ផ្ញើរួច'),
    ]
    cursor.executemany('''
        INSERT INTO documents (doc_number, doc_type, title, source_destination, doc_date, scanned_file, category, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', docs_data)

    # 11. Mission Orders
    missions_data = [
        ('524', 'ចូលរួមប្រជុំដំណើរការប្រជុំបច្ចេកទេសប្រចាំខែមិថុនា', 'ហួត ស', 'បឋម.សណ្តាន់', '2026-06-29', '2026-06-29', 'ចូលរួមប្រជុំបច្ចេកទេសប្រចាំខែ', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, ''),
        ('524-A', 'ចូលរួមប្រជុំដំណើរការប្រជុំបច្ចេកទេសប្រចាំខែមិថុនា', 'សៀម សារឿង', 'បឋម.សណ្តាន់', '2026-06-29', '2026-06-29', 'ចូលរួមប្រជុំបច្ចេកទេសប្រចាំខែ', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, ''),
        ('524-B', 'ចូលរួមប្រជុំដំណើរការប្រជុំបច្ចេកទេសប្រចាំខែមិថុនា', 'សែន ហួត', 'បឋម.សណ្តាន់', '2026-06-29', '2026-06-29', 'ចូលរួមប្រជុំបច្ចេកទេសប្រចាំខែ', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, ''),
        ('525', 'ចូលរួមគាំទ្រការប្រជុំបច្ចេកទេសនៅថ្ងៃព្រហស្បតិ៍ នៅក្នុងក្រុមសាលាស្រុក', 'ចក់ សុភាព', 'បឋម បុសសាងកែវ', '2026-06-29', '2026-06-29', 'ចូលរួមគាំទ្រការប្រជុំបច្ចេកទេស', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, ''),
        ('528', 'ចុះគាំទ្រការអនុវត្តច្បាប់សម្ភារៈបរិក្ខារ និងផលិតវិទ្យាសាស្ត្របង្រៀន និងពិសោធន៍', 'សៀម សារឿង', 'បឋម.តាប្រុក', '2026-06-30', '2026-06-30', 'ចុះគាំទ្រការអនុវត្តច្បាប់សម្ភារៈបរិក្ខារ', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, ''),
        ('528-A', 'ចុះគាំទ្រការអនុវត្តច្បាប់សម្ភារៈបរិក្ខារ និងផលិតវិទ្យាសាស្ត្របង្រៀន និងពិសោធន៍', 'ចក់ សុភាព', 'បឋម.តាប្រុក', '2026-06-30', '2026-06-30', 'ចុះគាំទ្រការអនុវត្តច្បាប់សម្ភារៈបរិក្ខារ', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, ''),
        ('528-B', 'ចុះគាំទ្រការអនុវត្តច្បាប់សម្ភារៈបរិក្ខារ និងផលិតវិទ្យាសាស្ត្របង្រៀន និងពិសោធន៍', 'សែន ហួត', 'បឋម.តាប្រុក', '2026-06-30', '2026-06-30', 'ចុះគាំទ្រការអនុវត្តច្បាប់សម្ភារៈបរិក្ខារ', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, ''),
        ('536', 'ចុះពិនិត្យតាមដានការបង្រៀន និងប្រជុំគណៈកម្មការសាលារើសសៀវភៅ', 'សៀម សារឿង', 'មធ្យម.ដូនឱ', '2026-07-06', '2026-07-06', 'ចុះពិនិត្យតាមដានការបង្រៀន', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, ''),
        ('536-A', 'ចុះពិនិត្យតាមដានការបង្រៀន និងប្រជុំគណៈកម្មការសាលារើសសៀវភៅ', 'ចក់ សុភាព', 'មធ្យម.ដូនឱ', '2026-07-06', '2026-07-06', 'ចុះពិនិត្យតាមដានការបង្រៀន', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, ''),
        ('536-B', 'ចុះពិនិត្យតាមដានការបង្រៀន និងប្រជុំគណៈកម្មការសាលារើសសៀវភៅ', 'សែន ហួត', 'មធ្យម.ដូនឱ', '2026-07-06', '2026-07-06', 'ចុះពិនិត្យតាមដានការបង្រៀន', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, ''),
        ('545', 'ចុះពិនិត្យតាមដានដំណើរការប្រឡងឆមាសលើកទី១', 'សៀម សារឿង', 'បឋម.លាងដៃ', '2026-07-12', '2026-07-12', 'ចុះពិនិត្យតាមដានដំណើរការប្រឡង', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, ''),
        ('545-A', 'ចុះពិនិត្យតាមដានដំណើរការប្រឡងឆមាសលើកទី១', 'ចក់ សុភាព', 'បឋម.លាងដៃ', '2026-07-12', '2026-07-12', 'ចុះពិនិត្យតាមដានដំណើរការប្រឡង', 'លោក រ៉ាត់ សំអឿន', 'approved', 40000.0, '')
    ]
    cursor.executemany('''
        INSERT INTO mission_orders (mission_code, title, officer_names, destination_schools, start_date, end_date, purpose, approved_by, status, allowance_amount, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', missions_data)

    # 12. Assets
    assets_data = [
        (1, 'តុ និងកៅអីសិស្ស', 'furniture', 450, 'good', '2024-10-01'),
        (1, 'កុំព្យូទ័រ Desktop សម្រាប់បន្ទប់កុំព្យូទ័រ', 'computer', 30, 'good', '2024-11-15'),
        (1, 'សៀវភៅសិក្សាមូលដ្ឋាន ថ្នាក់ទី១០-១២', 'textbook', 1200, 'good', '2025-01-05'),
        (2, 'តុ និងកៅអីសិស្ស', 'furniture', 220, 'repair_needed', '2023-09-01'),
        (2, 'កុំព្យូទ័រ Laptop សម្រាប់រដ្ឋបាល', 'computer', 5, 'good', '2024-05-10'),
        (4, 'តុ និងកៅអីសិស្ស', 'furniture', 280, 'good', '2024-08-20'),
        (5, 'សៀវភៅសិក្សាមូលដ្ឋាន ថ្នាក់ទី១-៦', 'textbook', 850, 'good', '2025-01-10'),
    ]
    cursor.executemany('''
        INSERT INTO assets (school_id, asset_name, category, quantity, condition, date_allocated)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', assets_data)

    # 13. Budgets
    budgets_data = [
        (1, '2025-2026', 'PB_operational', 45000000.0, 32000000.0, 'កញ្ចប់ថវិកាប្រតិបត្តិការសាលា (រៀល)'),
        (1, '2025-2026', 'school_development', 15000000.0, 10000000.0, 'ថវិកាអភិវឌ្ឍន៍សាលា'),
        (2, '2025-2026', 'PB_operational', 25000000.0, 18000000.0, 'កញ្ចប់ថវិកាប្រតិបត្តិការសាលា (រៀល)'),
        (3, '2025-2026', 'PB_operational', 22000000.0, 15000000.0, 'កញ្ចប់ថវិកាប្រតិបត្តិការសាលា (រៀល)'),
        (4, '2025-2026', 'PB_operational', 28000000.0, 20000000.0, 'កញ្ចប់ថវិកាប្រតិបត្តិការសាលា (រៀល)'),
        (5, '2025-2026', 'PB_operational', 24000000.0, 16500000.0, 'កញ្ចប់ថវិកាប្រតិបត្តិការសាលា (រៀល)'),
    ]
    cursor.executemany('''
        INSERT INTO budgets (school_id, academic_year, budget_type, allocated_amount, spent_amount, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', budgets_data)

    conn.commit()
    conn.close()
    print("Database successfully seeded with Angkor Thom District data.")

if __name__ == '__main__':
    seed_database()
