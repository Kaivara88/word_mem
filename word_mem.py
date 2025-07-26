import sys
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta, date
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import threading
import random

class TTSEngine:
    """文本转语音引擎"""
    def __init__(self):
        self.enabled = True
        self._lock = None
        self._speaking = False
        self.init_lock()
    
    def init_lock(self):
        """初始化线程锁"""
        try:
            import threading
            self._lock = threading.Lock()
        except Exception as e:
            print(f"⚠️ 线程锁初始化失败: {e}")
    
    def create_engine(self):
        """创建新的TTS引擎实例"""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            
            # 设置语音属性
            voices = engine.getProperty('voices')
            # 尝试设置英语语音
            for voice in voices:
                if 'english' in voice.name.lower() or 'en' in voice.id.lower():
                    engine.setProperty('voice', voice.id)
                    break
            
            # 设置语速和音量
            engine.setProperty('rate', 150)  # 语速
            engine.setProperty('volume', 0.8)  # 音量
            
            return engine
        except Exception as e:
            print(f"⚠️ TTS引擎创建失败: {e}")
            return None
    
    def cleanup_engine(self, engine):
        """清理TTS引擎资源"""
        try:
            if engine:
                engine.stop()
                # 尝试删除引擎实例
                del engine
        except Exception as e:
            print(f"⚠️ TTS引擎清理失败: {e}")
    
    def speak(self, text):
        """播放语音 - 每次都创建新的引擎实例"""
        if not self.enabled or not text:
            return
            
        # 防止重复播放
        if self._speaking:
            return
            
        try:
            import threading
            
            def speak_thread():
                engine = None
                try:
                    with self._lock:
                        if self._speaking:  # 双重检查
                            return
                        self._speaking = True
                    
                    # 创建新的引擎实例
                    engine = self.create_engine()
                    if not engine:
                        return
                    
                    # 播放语音
                    engine.say(text)
                    engine.runAndWait()
                    print(f"🔊 播放发音: {text}")
                    
                except Exception as e:
                    print(f"⚠️ 语音播放失败: {e}")
                finally:
                    # 清理引擎资源
                    self.cleanup_engine(engine)
                    # 重置状态
                    with self._lock:
                        self._speaking = False
            
            thread = threading.Thread(target=speak_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            print(f"⚠️ 语音播放失败: {e}")
            with self._lock:
                self._speaking = False
    
    def is_available(self):
        """检查TTS是否可用"""
        try:
            import pyttsx3
            test_engine = pyttsx3.init()
            if test_engine:
                test_engine.stop()
                del test_engine
                return True
        except:
            pass
        return False

class UserDatabase:
    """用户数据库管理"""
    def __init__(self, db_path="word_memory_users.db"):
        self.db_path = db_path
        self.current_user_id = None
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # 单词表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                pronunciation TEXT,
                meaning TEXT NOT NULL,
                level TEXT DEFAULT '初级',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 用户单词学习记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_word_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,
                review_count INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                difficulty INTEGER DEFAULT 1,
                last_review_date TIMESTAMP,
                next_review_date TIMESTAMP,
                mastery_level INTEGER DEFAULT 0,
                consecutive_correct INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (word_id) REFERENCES words (id),
                UNIQUE(user_id, word_id)
            )
        ''')
        
        # 学习记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,
                study_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_correct BOOLEAN NOT NULL,
                study_mode TEXT NOT NULL,
                response_time REAL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (word_id) REFERENCES words (id)
            )
        ''')
        
        # 用户设置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                setting_key TEXT NOT NULL,
                setting_value TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, setting_key)
            )
        ''')
        
        # 系统状态表 - 新增
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                state_key TEXT NOT NULL,
                state_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, state_key)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # 执行数据库迁移
        self.migrate_database()
        
        # 初始化默认单词库
        self.init_default_words()
        
        # 初始化admin用户
        self.init_admin_user()
    
    def migrate_database(self):
        """数据库迁移 - 添加新字段"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 检查consecutive_correct字段是否存在
            cursor.execute("PRAGMA table_info(user_word_progress)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'consecutive_correct' not in columns:
                cursor.execute('''
                    ALTER TABLE user_word_progress 
                    ADD COLUMN consecutive_correct INTEGER DEFAULT 0
                ''')
                print("✅ 数据库已升级：添加连续正确次数字段")
                
        except sqlite3.Error as e:
            print(f"⚠️ 数据库迁移警告: {e}")
        
        conn.commit()
        conn.close()
    
    def init_admin_user(self):
        """初始化admin用户"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 检查是否已有admin用户
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if cursor.fetchone():
            conn.close()
            return
        
        # 创建admin用户
        password_hash = self.hash_password("admin123")
        cursor.execute('''
            INSERT INTO users (username, password_hash, email)
            VALUES (?, ?, ?)
        ''', ("admin", password_hash, "admin@wordmemory.com"))
        
        conn.commit()
        conn.close()
        print("✅ Admin用户已创建 - 用户名: admin, 密码: admin123")
        
        # 初始化默认单词库
        self.init_default_words()
        
        # 初始化admin用户
        self.init_admin_user()
    
    def init_default_words(self):
        """初始化默认单词库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 检查是否已有单词
        cursor.execute("SELECT COUNT(*) FROM words")
        if cursor.fetchone()[0] > 0:
            conn.close()
            return
        
        # 默认单词库 - 按教育阶段分级
        default_words = [
            # 小学词汇 (基础生活词汇)
            ("cat", "/kæt/", "猫", "小学"),
            ("dog", "/dɔːɡ/", "狗", "小学"),
            ("book", "/bʊk/", "书", "小学"),
            ("pen", "/pen/", "钢笔", "小学"),
            ("apple", "/ˈæpl/", "苹果", "小学"),
            ("water", "/ˈwɔːtər/", "水", "小学"),
            ("food", "/fuːd/", "食物", "小学"),
            ("house", "/haʊs/", "房子", "小学"),
            ("car", "/kɑːr/", "汽车", "小学"),
            ("tree", "/triː/", "树", "小学"),
            ("sun", "/sʌn/", "太阳", "小学"),
            ("moon", "/muːn/", "月亮", "小学"),
            ("star", "/stɑːr/", "星星", "小学"),
            ("red", "/red/", "红色", "小学"),
            ("blue", "/bluː/", "蓝色", "小学"),
            ("green", "/ɡriːn/", "绿色", "小学"),
            ("big", "/bɪɡ/", "大的", "小学"),
            ("small", "/smɔːl/", "小的", "小学"),
            ("good", "/ɡʊd/", "好的", "小学"),
            ("bad", "/bæd/", "坏的", "小学"),
            ("happy", "/ˈhæpi/", "快乐的", "小学"),
            ("sad", "/sæd/", "悲伤的", "小学"),
            ("run", "/rʌn/", "跑", "小学"),
            ("walk", "/wɔːk/", "走", "小学"),
            ("eat", "/iːt/", "吃", "小学"),
            ("drink", "/drɪŋk/", "喝", "小学"),
            ("sleep", "/sliːp/", "睡觉", "小学"),
            ("play", "/pleɪ/", "玩", "小学"),
            ("work", "/wɜːrk/", "工作", "小学"),
            ("love", "/lʌv/", "爱", "小学"),
            ("family", "/ˈfæməli/", "家庭", "小学"),
            ("friend", "/frend/", "朋友", "小学"),
            ("mother", "/ˈmʌðər/", "母亲", "小学"),
            ("father", "/ˈfɑːðər/", "父亲", "小学"),
            ("brother", "/ˈbrʌðər/", "兄弟", "小学"),
            ("sister", "/ˈsɪstər/", "姐妹", "小学"),
            ("boy", "/bɔɪ/", "男孩", "小学"),
            ("girl", "/ɡɜːrl/", "女孩", "小学"),
            ("man", "/mæn/", "男人", "小学"),
            ("woman", "/ˈwʊmən/", "女人", "小学"),
            
            # 初中词汇 (学科和日常扩展词汇)
            ("computer", "/kəmˈpjuːtər/", "电脑", "初中"),
            ("internet", "/ˈɪntərnet/", "互联网", "初中"),
            ("telephone", "/ˈteləfoʊn/", "电话", "初中"),
            ("television", "/ˈteləvɪʒn/", "电视", "初中"),
            ("music", "/ˈmjuːzɪk/", "音乐", "初中"),
            ("movie", "/ˈmuːvi/", "电影", "初中"),
            ("sport", "/spɔːrt/", "运动", "初中"),
            ("football", "/ˈfʊtbɔːl/", "足球", "初中"),
            ("basketball", "/ˈbæskɪtbɔːl/", "篮球", "初中"),
            ("swimming", "/ˈswɪmɪŋ/", "游泳", "初中"),
            ("science", "/ˈsaɪəns/", "科学", "初中"),
            ("mathematics", "/ˌmæθəˈmætɪks/", "数学", "初中"),
            ("history", "/ˈhɪstəri/", "历史", "初中"),
            ("geography", "/dʒiˈɑːɡrəfi/", "地理", "初中"),
            ("biology", "/baɪˈɑːlədʒi/", "生物", "初中"),
            ("chemistry", "/ˈkeməstri/", "化学", "初中"),
            ("physics", "/ˈfɪzɪks/", "物理", "初中"),
            ("memory", "/ˈmeməri/", "记忆", "初中"),
            ("language", "/ˈlæŋɡwɪdʒ/", "语言", "初中"),
            ("practice", "/ˈpræktɪs/", "练习", "初中"),
            ("knowledge", "/ˈnɑːlɪdʒ/", "知识", "初中"),
            ("education", "/ˌedʒuˈkeɪʃn/", "教育", "初中"),
            ("student", "/ˈstuːdnt/", "学生", "初中"),
            ("teacher", "/ˈtiːtʃər/", "老师", "初中"),
            ("school", "/skuːl/", "学校", "初中"),
            ("library", "/ˈlaɪbreri/", "图书馆", "初中"),
            ("hospital", "/ˈhɑːspɪtl/", "医院", "初中"),
            ("restaurant", "/ˈrestərɑːnt/", "餐厅", "初中"),
            ("supermarket", "/ˈsuːpərmɑːrkɪt/", "超市", "初中"),
            ("airport", "/ˈerpɔːrt/", "机场", "初中"),
            ("station", "/ˈsteɪʃn/", "车站", "初中"),
            ("country", "/ˈkʌntri/", "国家", "初中"),
            ("city", "/ˈsɪti/", "城市", "初中"),
            ("village", "/ˈvɪlɪdʒ/", "村庄", "初中"),
            ("mountain", "/ˈmaʊntən/", "山", "初中"),
            ("river", "/ˈrɪvər/", "河", "初中"),
            ("ocean", "/ˈoʊʃn/", "海洋", "初中"),
            ("weather", "/ˈweðər/", "天气", "初中"),
            ("season", "/ˈsiːzn/", "季节", "初中"),
            ("spring", "/sprɪŋ/", "春天", "初中"),
            ("summer", "/ˈsʌmər/", "夏天", "初中"),
            ("autumn", "/ˈɔːtəm/", "秋天", "初中"),
            ("winter", "/ˈwɪntər/", "冬天", "初中"),
            
            # 高中词汇 (学术和抽象概念)
            ("achievement", "/əˈtʃiːvmənt/", "成就", "高中"),
            ("opportunity", "/ˌɑːpərˈtuːnəti/", "机会", "高中"),
            ("experience", "/ɪkˈspɪriəns/", "经验", "高中"),
            ("development", "/dɪˈveləpmənt/", "发展", "高中"),
            ("environment", "/ɪnˈvaɪrənmənt/", "环境", "高中"),
            ("technology", "/tekˈnɑːlədʒi/", "技术", "高中"),
            ("information", "/ˌɪnfərˈmeɪʃn/", "信息", "高中"),
            ("communication", "/kəˌmjuːnɪˈkeɪʃn/", "交流", "高中"),
            ("organization", "/ˌɔːrɡənəˈzeɪʃn/", "组织", "高中"),
            ("responsibility", "/rɪˌspɑːnsəˈbɪləti/", "责任", "高中"),
            ("government", "/ˈɡʌvərnmənt/", "政府", "高中"),
            ("democracy", "/dɪˈmɑːkrəsi/", "民主", "高中"),
            ("economy", "/ɪˈkɑːnəmi/", "经济", "高中"),
            ("society", "/səˈsaɪəti/", "社会", "高中"),
            ("culture", "/ˈkʌltʃər/", "文化", "高中"),
            ("tradition", "/trəˈdɪʃn/", "传统", "高中"),
            ("literature", "/ˈlɪtərətʃər/", "文学", "高中"),
            ("philosophy", "/fəˈlɑːsəfi/", "哲学", "高中"),
            ("psychology", "/saɪˈkɑːlədʒi/", "心理学", "高中"),
            ("sociology", "/ˌsoʊsiˈɑːlədʒi/", "社会学", "高中"),
            ("anthropology", "/ˌænθrəˈpɑːlədʒi/", "人类学", "高中"),
            ("archaeology", "/ˌɑːrkiˈɑːlədʒi/", "考古学", "高中"),
            ("architecture", "/ˈɑːrkɪtektʃər/", "建筑学", "高中"),
            ("engineering", "/ˌendʒɪˈnɪrɪŋ/", "工程学", "高中"),
            ("medicine", "/ˈmedsn/", "医学", "高中"),
            ("agriculture", "/ˈæɡrɪkʌltʃər/", "农业", "高中"),
            ("industry", "/ˈɪndəstri/", "工业", "高中"),
            ("commerce", "/ˈkɑːmərs/", "商业", "高中"),
            ("finance", "/ˈfaɪnæns/", "金融", "高中"),
            ("investment", "/ɪnˈvestmənt/", "投资", "高中"),
            ("management", "/ˈmænɪdʒmənt/", "管理", "高中"),
            ("leadership", "/ˈliːdərʃɪp/", "领导力", "高中"),
            ("innovation", "/ˌɪnəˈveɪʃn/", "创新", "高中"),
            ("creativity", "/ˌkriːeɪˈtɪvəti/", "创造力", "高中"),
            ("imagination", "/ɪˌmædʒɪˈneɪʃn/", "想象力", "高中"),
            ("intelligence", "/ɪnˈtelɪdʒəns/", "智力", "高中"),
            ("wisdom", "/ˈwɪzdəm/", "智慧", "高中"),
            ("courage", "/ˈkɜːrɪdʒ/", "勇气", "高中"),
            ("patience", "/ˈpeɪʃns/", "耐心", "高中"),
            ("perseverance", "/ˌpɜːrsəˈvɪrəns/", "毅力", "高中"),
            ("determination", "/dɪˌtɜːrmɪˈneɪʃn/", "决心", "高中"),
            
            # 大学词汇 (专业和高级概念)
            ("sophisticated", "/səˈfɪstɪkeɪtɪd/", "复杂的", "大学"),
            ("comprehensive", "/ˌkɑːmprɪˈhensɪv/", "全面的", "大学"),
            ("extraordinary", "/ɪkˈstrɔːrdəneri/", "非凡的", "大学"),
            ("revolutionary", "/ˌrevəˈluːʃəneri/", "革命性的", "大学"),
            ("unprecedented", "/ʌnˈpresɪdentɪd/", "史无前例的", "大学"),
            ("philosophical", "/ˌfɪləˈsɑːfɪkl/", "哲学的", "大学"),
            ("psychological", "/ˌsaɪkəˈlɑːdʒɪkl/", "心理的", "大学"),
            ("entrepreneurial", "/ˌɑːntrəprəˈnɜːriəl/", "企业家的", "大学"),
            ("interdisciplinary", "/ˌɪntərdɪsəˈplɪneri/", "跨学科的", "大学"),
            ("metamorphosis", "/ˌmetəˈmɔːrfəsɪs/", "变形", "大学"),
            ("paradigm", "/ˈpærədaɪm/", "范式", "大学"),
            ("hypothesis", "/haɪˈpɑːθəsɪs/", "假设", "大学"),
            ("methodology", "/ˌmeθəˈdɑːlədʒi/", "方法论", "大学"),
            ("epistemology", "/ɪˌpɪstəˈmɑːlədʒi/", "认识论", "大学"),
            ("phenomenology", "/fɪˌnɑːməˈnɑːlədʒi/", "现象学", "大学"),
            ("existentialism", "/ɪɡˌzɪstenʃəˈlɪzəm/", "存在主义", "大学"),
            ("postmodernism", "/ˌpoʊstˈmɑːdərnɪzəm/", "后现代主义", "大学"),
            ("globalization", "/ˌɡloʊbələˈzeɪʃn/", "全球化", "大学"),
            ("sustainability", "/səˌsteɪnəˈbɪləti/", "可持续性", "大学"),
            ("biodiversity", "/ˌbaɪoʊdaɪˈvɜːrsəti/", "生物多样性", "大学"),
            ("biotechnology", "/ˌbaɪoʊtekˈnɑːlədʒi/", "生物技术", "大学"),
            ("nanotechnology", "/ˌnænoʊtekˈnɑːlədʒi/", "纳米技术", "大学"),
            ("artificial intelligence", "/ˌɑːrtɪˈfɪʃl ɪnˈtelɪdʒəns/", "人工智能", "大学"),
            ("quantum mechanics", "/ˈkwɑːntəm məˈkænɪks/", "量子力学", "大学"),
            ("thermodynamics", "/ˌθɜːrmoʊdaɪˈnæmɪks/", "热力学", "大学"),
            ("electromagnetic", "/ɪˌlektroʊmæɡˈnetɪk/", "电磁的", "大学"),
            ("photosynthesis", "/ˌfoʊtoʊˈsɪnθəsɪs/", "光合作用", "大学"),
            ("metabolism", "/məˈtæbəlɪzəm/", "新陈代谢", "大学"),
            ("chromosome", "/ˈkroʊməsoʊm/", "染色体", "大学"),
            ("mitochondria", "/ˌmaɪtəˈkɑːndriə/", "线粒体", "大学"),
            ("neuroscience", "/ˈnʊroʊsaɪəns/", "神经科学", "大学"),
            ("cognitive", "/ˈkɑːɡnətɪv/", "认知的", "大学"),
            ("consciousness", "/ˈkɑːnʃəsnəs/", "意识", "大学"),
            ("subconscious", "/sʌbˈkɑːnʃəs/", "潜意识", "大学"),
            ("psychoanalysis", "/ˌsaɪkoʊəˈnæləsɪs/", "精神分析", "大学"),
            ("behaviorism", "/bɪˈheɪvjərɪzəm/", "行为主义", "大学"),
            ("constructivism", "/kənˈstrʌktɪvɪzəm/", "建构主义", "大学"),
            ("empiricism", "/ɪmˈpɪrɪsɪzəm/", "经验主义", "大学"),
            ("rationalism", "/ˈræʃnəlɪzəm/", "理性主义", "大学"),
            ("dialectical", "/ˌdaɪəˈlektɪkl/", "辩证的", "大学"),
            ("synthesis", "/ˈsɪnθəsɪs/", "综合", "大学"),
            ("antithesis", "/ænˈtɪθəsɪs/", "对立", "大学"),
            ("juxtaposition", "/ˌdʒʌkstəpəˈzɪʃn/", "并置", "大学")
        ]
        
        for word, pronunciation, meaning, level in default_words:
            cursor.execute('''
                INSERT INTO words (word, pronunciation, meaning, level)
                VALUES (?, ?, ?, ?)
            ''', (word, pronunciation, meaning, level))
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password):
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, username, password, email=""):
        """注册用户"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            password_hash = self.hash_password(password)
            cursor.execute('''
                INSERT INTO users (username, password_hash, email)
                VALUES (?, ?, ?)
            ''', (username, password_hash, email))
            
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return user_id
        except sqlite3.IntegrityError:
            conn.close()
            return None
    
    def login_user(self, username, password):
        """用户登录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        password_hash = self.hash_password(password)
        cursor.execute('''
            SELECT id FROM users 
            WHERE username = ? AND password_hash = ?
        ''', (username, password_hash))
        
        result = cursor.fetchone()
        if result:
            user_id = result[0]
            # 更新最后登录时间
            cursor.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (user_id,))
            conn.commit()
            self.current_user_id = user_id
        
        conn.close()
        return result is not None
    
    def get_user_info(self, user_id=None):
        """获取用户信息"""
        if user_id is None:
            user_id = self.current_user_id
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, email, created_at, last_login 
            FROM users WHERE id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        return result
    
    def get_words_for_review(self, limit=10, level=None):
        """获取需要复习的单词"""
        if not self.current_user_id:
            return []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取用户需要复习的单词，排除已经连续三次正确的单词
        query = '''
            SELECT w.id, w.word, w.pronunciation, w.meaning, w.level,
                   COALESCE(uwp.review_count, 0) as review_count,
                   COALESCE(uwp.correct_count, 0) as correct_count,
                   COALESCE(uwp.difficulty, 1) as difficulty,
                   COALESCE(uwp.mastery_level, 0) as mastery_level,
                   COALESCE(uwp.consecutive_correct, 0) as consecutive_correct
            FROM words w
            LEFT JOIN user_word_progress uwp ON w.id = uwp.word_id AND uwp.user_id = ?
            WHERE (uwp.next_review_date IS NULL OR uwp.next_review_date <= ?)
            AND COALESCE(uwp.consecutive_correct, 0) < 3
        '''
        
        params = [self.current_user_id, datetime.now()]
        
        if level:
            query += ' AND w.level = ?'
            params.append(level)
        
        query += ' ORDER BY COALESCE(uwp.next_review_date, w.created_at) ASC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        words = cursor.fetchall()
        conn.close()
        return words
    
    def update_word_progress(self, word_id, is_correct, study_mode):
        """更新单词学习进度 - 智能记忆算法"""
        if not self.current_user_id:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取或创建用户单词进度记录
        cursor.execute('''
            SELECT review_count, correct_count, difficulty, mastery_level, consecutive_correct
            FROM user_word_progress 
            WHERE user_id = ? AND word_id = ?
        ''', (self.current_user_id, word_id))
        
        result = cursor.fetchone()
        if result:
            review_count, correct_count, difficulty, mastery_level, consecutive_correct = result
        else:
            review_count, correct_count, difficulty, mastery_level, consecutive_correct = 0, 0, 1, 0, 0
        
        # 更新统计
        review_count += 1
        
        if is_correct:
            correct_count += 1
            consecutive_correct += 1
            mastery_level = min(5, mastery_level + 1)
            difficulty = max(1, difficulty - 1)
        else:
            consecutive_correct = 0  # 重置连续正确次数
            mastery_level = max(0, mastery_level - 1)
            difficulty = min(5, difficulty + 1)
        
        # 智能复习时间计算
        if consecutive_correct >= 3:
            # 连续三次正确，停止记忆（设置很远的复习时间）
            next_review = datetime.now() + timedelta(days=365)  # 一年后
            mastery_level = 5  # 标记为完全掌握
        elif is_correct:
            # 正确答案 - 使用记忆曲线
            if mastery_level <= 1:
                next_review = datetime.now() + timedelta(minutes=20)  # 20分钟后
            elif mastery_level == 2:
                next_review = datetime.now() + timedelta(hours=1)    # 1小时后
            elif mastery_level == 3:
                next_review = datetime.now() + timedelta(hours=8)    # 8小时后
            elif mastery_level == 4:
                next_review = datetime.now() + timedelta(days=1)     # 1天后
            else:
                next_review = datetime.now() + timedelta(days=2)     # 2天后
        else:
            # 错误答案 - 加入重复记忆
            if difficulty >= 4:
                next_review = datetime.now() + timedelta(minutes=5)   # 5分钟后重复
            elif difficulty >= 3:
                next_review = datetime.now() + timedelta(minutes=10)  # 10分钟后重复
            else:
                next_review = datetime.now() + timedelta(minutes=15)  # 15分钟后重复
        
        # 更新或插入进度记录
        cursor.execute('''
            INSERT OR REPLACE INTO user_word_progress 
            (user_id, word_id, review_count, correct_count, difficulty, 
             last_review_date, next_review_date, mastery_level, consecutive_correct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (self.current_user_id, word_id, review_count, correct_count, 
              difficulty, datetime.now(), next_review, mastery_level, consecutive_correct))
        
        # 添加学习记录
        cursor.execute('''
            INSERT INTO study_records 
            (user_id, word_id, is_correct, study_mode)
            VALUES (?, ?, ?, ?)
        ''', (self.current_user_id, word_id, is_correct, study_mode))
        
        conn.commit()
        conn.close()
    
    def get_user_statistics(self):
        """获取用户学习统计"""
        if not self.current_user_id:
            return {}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总单词数
        cursor.execute('SELECT COUNT(*) FROM words')
        total_words = cursor.fetchone()[0]
        
        # 已学习单词数
        cursor.execute('''
            SELECT COUNT(*) FROM user_word_progress 
            WHERE user_id = ? AND review_count > 0
        ''', (self.current_user_id,))
        studied_words = cursor.fetchone()[0]
        
        # 已掌握单词数（连续三次正确）
        cursor.execute('''
            SELECT COUNT(*) FROM user_word_progress 
            WHERE user_id = ? AND consecutive_correct >= 3
        ''', (self.current_user_id,))
        mastered_words = cursor.fetchone()[0]
        
        # 今日学习数
        today = date.today()
        cursor.execute('''
            SELECT COUNT(DISTINCT word_id) FROM study_records 
            WHERE user_id = ? AND DATE(study_date) = ?
        ''', (self.current_user_id, today))
        today_studied = cursor.fetchone()[0]
        
        # 正确率
        cursor.execute('''
            SELECT AVG(CAST(is_correct AS FLOAT)) * 100 FROM study_records 
            WHERE user_id = ?
        ''', (self.current_user_id,))
        accuracy = cursor.fetchone()[0] or 0
        
        # 掌握程度分布
        cursor.execute('''
            SELECT mastery_level, COUNT(*) FROM user_word_progress 
            WHERE user_id = ? GROUP BY mastery_level
        ''', (self.current_user_id,))
        mastery_distribution = dict(cursor.fetchall())
        
        # 连续正确次数分布
        cursor.execute('''
            SELECT consecutive_correct, COUNT(*) FROM user_word_progress 
            WHERE user_id = ? AND review_count > 0 GROUP BY consecutive_correct
        ''', (self.current_user_id,))
        consecutive_distribution = dict(cursor.fetchall())
        
        conn.close()
        return {
            'total_words': total_words,
            'studied_words': studied_words,
            'mastered_words': mastered_words,
            'today_studied': today_studied,
            'accuracy': round(accuracy, 1),
            'mastery_distribution': mastery_distribution,
            'consecutive_distribution': consecutive_distribution
        }
    
    def save_system_state(self, key, value):
        """保存系统状态"""
        if not self.current_user_id:
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 使用INSERT OR REPLACE来更新或插入
        cursor.execute('''
            INSERT OR REPLACE INTO system_state (user_id, state_key, state_value)
            VALUES (?, ?, ?)
        ''', (self.current_user_id, key, json.dumps(value)))
        
        conn.commit()
        conn.close()
        return True
    
    def load_system_state(self, key, default_value=None):
        """加载系统状态"""
        if not self.current_user_id:
            return default_value
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT state_value FROM system_state 
            WHERE user_id = ? AND state_key = ?
        ''', (self.current_user_id, key))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            try:
                return json.loads(result[0])
            except json.JSONDecodeError:
                return default_value
        return default_value
    
    def get_all_system_states(self):
        """获取所有系统状态"""
        if not self.current_user_id:
            return {}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT state_key, state_value FROM system_state 
            WHERE user_id = ?
        ''', (self.current_user_id,))
        
        states = {}
        for key, value in cursor.fetchall():
            try:
                states[key] = json.loads(value)
            except json.JSONDecodeError:
                states[key] = value
        
        conn.close()
        return states
    
    def clear_system_state(self, key=None):
        """清除系统状态"""
        if not self.current_user_id:
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if key:
            cursor.execute('''
                DELETE FROM system_state 
                WHERE user_id = ? AND state_key = ?
            ''', (self.current_user_id, key))
        else:
            cursor.execute('''
                DELETE FROM system_state WHERE user_id = ?
            ''', (self.current_user_id,))
        
        conn.commit()
        conn.close()
        return True

class LoginDialog(QDialog):
    """登录对话框"""
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("单词记忆助手 - 用户登录")
        self.setFixedSize(450, 400)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #667eea, stop:1 #764ba2);
            }
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QLineEdit {
                padding: 15px;
                border: 2px solid white;
                border-radius: 10px;
                background-color: rgba(255,255,255,0.95);
                font-size: 16px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 3px solid #f1c40f;
                background-color: white;
            }
            QPushButton {
                padding: 15px 20px;
                border: none;
                border-radius: 10px;
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                font-size: 16px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(25)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # 标题
        title = QLabel("🎓 单词记忆助手")
        title.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(title)
        
        # 用户名
        username_label = QLabel("用户名:")
        username_label.setFont(QFont("Microsoft YaHei", 12))
        layout.addWidget(username_label)
        
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("请输入用户名")
        layout.addWidget(self.username_edit)
        
        # 密码
        password_label = QLabel("密码:")
        password_label.setFont(QFont("Microsoft YaHei", 12))
        layout.addWidget(password_label)
        
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("请输入密码")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_edit)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.login_button = QPushButton("登录")
        self.login_button.clicked.connect(self.login)
        button_layout.addWidget(self.login_button)
        
        self.register_button = QPushButton("注册")
        self.register_button.clicked.connect(self.register)
        button_layout.addWidget(self.register_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 回车登录
        self.password_edit.returnPressed.connect(self.login)
    
    def login(self):
        """登录"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        
        if not username or not password:
            QMessageBox.warning(self, "错误", "请输入用户名和密码！")
            return
        
        if self.db.login_user(username, password):
            self.accept()
        else:
            QMessageBox.warning(self, "登录失败", "用户名或密码错误！")
    
    def register(self):
        """注册"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        
        if not username or not password:
            QMessageBox.warning(self, "错误", "请输入用户名和密码！")
            return
        
        if len(password) < 6:
            QMessageBox.warning(self, "错误", "密码长度至少6位！")
            return
        
        user_id = self.db.register_user(username, password)
        if user_id:
            QMessageBox.information(self, "注册成功", "用户注册成功！请登录。")
            # 自动登录
            self.db.login_user(username, password)
            self.accept()
        else:
            QMessageBox.warning(self, "注册失败", "用户名已存在！")

class StudyWidget(QWidget):
    """学习界面"""
    word_completed = pyqtSignal(int, bool, str)  # word_id, is_correct, study_mode
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_word = None
        self.current_words = []
        self.current_index = 0
        self.study_mode = "spelling"
        self.tts_engine = TTSEngine()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 学习模式选择
        mode_group = QGroupBox("🎯 学习模式")
        mode_group.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        mode_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #f8f9fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px 0 10px;
                color: #2c3e50;
            }
        """)
        
        mode_layout = QHBoxLayout()
        
        self.spelling_mode = QCheckBox("✏️ 拼写练习")
        self.spelling_mode.setChecked(True)
        self.spelling_mode.toggled.connect(self.on_mode_changed)
        
        self.meaning_mode = QCheckBox("📖 词义练习")
        self.meaning_mode.toggled.connect(self.on_mode_changed)
        
        mode_layout.addWidget(self.spelling_mode)
        mode_layout.addWidget(self.meaning_mode)
        mode_layout.addStretch()
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # 难度选择
        level_group = QGroupBox("📊 难度选择")
        level_group.setStyleSheet(mode_group.styleSheet())
        level_layout = QHBoxLayout()
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["全部", "基础", "初级", "中级", "高级"])
        self.level_combo.currentTextChanged.connect(self.on_level_changed)
        self.level_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:focus {
                border: 2px solid #3498db;
            }
        """)
        
        level_layout.addWidget(QLabel("选择难度:"))
        level_layout.addWidget(self.level_combo)
        level_layout.addStretch()
        level_group.setLayout(level_layout)
        layout.addWidget(level_group)
        
        # 单词显示区域
        word_container = QWidget()
        word_container.setStyleSheet("""
            QWidget {
                background-color: #667eea;
                border-radius: 20px;
                margin: 10px;
            }
        """)
        word_layout = QVBoxLayout(word_container)
        word_layout.setContentsMargins(40, 30, 40, 30)
        
        self.word_label = QLabel("🎓 点击开始学习")
        self.word_label.setFont(QFont("Microsoft YaHei", 28, QFont.Weight.Bold))
        self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_label.setStyleSheet("""
            QLabel {
                color: white;
                background: transparent;
                padding: 20px;
                border-radius: 15px;
            }
        """)
        word_layout.addWidget(self.word_label)
        
        # 发音显示
        pronunciation_container = QWidget()
        pronunciation_container.setStyleSheet("background: transparent;")
        pronunciation_layout = QHBoxLayout(pronunciation_container)
        
        self.pronunciation_label = QLabel("")
        self.pronunciation_label.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        self.pronunciation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pronunciation_label.setStyleSheet("""
            QLabel {
                color: #f1c40f;
                background-color: rgba(255,255,255,0.1);
                padding: 10px 20px;
                border-radius: 25px;
                border: 2px solid rgba(255,255,255,0.2);
            }
        """)
        
        self.play_button = QPushButton("🔊")
        self.play_button.setFont(QFont("Arial", 16))
        self.play_button.clicked.connect(self.play_pronunciation)
        self.play_button.setFixedSize(50, 50)
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                border: 2px solid rgba(255,255,255,0.3);
                border-radius: 25px;
                color: white;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.3);
            }
        """)
        
        pronunciation_layout.addStretch()
        pronunciation_layout.addWidget(self.pronunciation_label)
        pronunciation_layout.addWidget(self.play_button)
        pronunciation_layout.addStretch()
        
        word_layout.addWidget(pronunciation_container)
        layout.addWidget(word_container)
        
        # 输入区域
        input_container = QWidget()
        input_layout = QVBoxLayout(input_container)
        
        input_label = QLabel("💭 请输入答案")
        input_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        input_label.setStyleSheet("color: #34495e; margin-left: 5px;")
        input_layout.addWidget(input_label)
        
        self.input_edit = QLineEdit()
        self.input_edit.setFont(QFont("Microsoft YaHei", 16))
        self.input_edit.setPlaceholderText("在这里输入答案...")
        self.input_edit.returnPressed.connect(self.check_answer)
        self.input_edit.setStyleSheet("""
            QLineEdit {
                padding: 15px 20px;
                border: 3px solid #bdc3c7;
                border-radius: 15px;
                background-color: white;
                font-size: 16px;
                color: #2c3e50;
            }
            QLineEdit:focus {
                border: 3px solid #3498db;
                background-color: #f8f9fa;
            }
        """)
        input_layout.addWidget(self.input_edit)
        layout.addWidget(input_container)
        
        # 按钮区域
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(15)
        
        self.start_button = QPushButton("🚀 开始学习")
        self.start_button.clicked.connect(self.start_study)
        self.start_button.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        self.start_button.setFixedHeight(50)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                border: none;
                border-radius: 25px;
                color: white;
                padding: 0 30px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        
        self.check_button = QPushButton("✅ 检查答案")
        self.check_button.clicked.connect(self.check_answer)
        self.check_button.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.check_button.setFixedHeight(45)
        self.check_button.setEnabled(False)
        self.check_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                border: none;
                border-radius: 22px;
                color: white;
                padding: 0 25px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        
        self.show_answer_button = QPushButton("💡 显示答案")
        self.show_answer_button.clicked.connect(self.show_answer)
        self.show_answer_button.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.show_answer_button.setFixedHeight(45)
        self.show_answer_button.setEnabled(False)
        self.show_answer_button.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                border: none;
                border-radius: 22px;
                color: white;
                padding: 0 25px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        
        self.next_button = QPushButton("➡️ 下一个")
        self.next_button.clicked.connect(self.next_word)
        self.next_button.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.next_button.setFixedHeight(45)
        self.next_button.setEnabled(False)
        self.next_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                border: none;
                border-radius: 22px;
                color: white;
                padding: 0 25px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.check_button)
        button_layout.addWidget(self.show_answer_button)
        button_layout.addWidget(self.next_button)
        layout.addWidget(button_container)
        
        # 结果显示
        self.result_label = QLabel("")
        self.result_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setMinimumHeight(60)
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #ecf0f1;
                border-radius: 15px;
                padding: 15px;
                margin: 10px 0;
            }
        """)
        layout.addWidget(self.result_label)
        
        self.setLayout(layout)
    
    def on_mode_changed(self):
        """模式改变"""
        if self.spelling_mode.isChecked() and self.meaning_mode.isChecked():
            self.study_mode = "mixed"
        elif self.spelling_mode.isChecked():
            self.study_mode = "spelling"
        elif self.meaning_mode.isChecked():
            self.study_mode = "meaning"
        else:
            self.spelling_mode.setChecked(True)
            self.study_mode = "spelling"
        
        # 保存学习模式状态
        mode_text = "混合模式" if self.study_mode == "mixed" else ("拼写练习" if self.study_mode == "spelling" else "词义练习")
        self.db.save_system_state('study_mode', mode_text)
    
    def on_level_changed(self, level_text):
        """难度级别改变"""
        self.db.save_system_state('difficulty_level', level_text)
    
    def start_study(self):
        """开始学习"""
        level = self.level_combo.currentText()
        if level == "全部":
            level = None
        
        self.current_words = self.db.get_words_for_review(limit=10, level=level)
        
        if not self.current_words:
            QMessageBox.information(self, "提示", "没有可学习的单词！\n请稍后再试或选择其他难度。")
            return
        
        self.current_index = 0
        self.start_button.setText("学习中...")
        self.start_button.setEnabled(False)
        
        word_data = self.current_words[self.current_index]
        self.set_word(word_data)
    
    def set_word(self, word_data):
        """设置当前单词"""
        self.current_word = word_data
        word_id, word, pronunciation, meaning, level = word_data[:5]
        
        # 随机选择模式（如果是混合模式）
        if self.study_mode == "mixed":
            current_mode = random.choice(["spelling", "meaning"])
        else:
            current_mode = self.study_mode
        
        if current_mode == "spelling":
            self.word_label.setText(f"📖 {meaning}")
            self.input_edit.setPlaceholderText("请输入英文单词...")
        else:
            self.word_label.setText(f"🔤 {word}")
            self.input_edit.setPlaceholderText("请输入中文意思...")
        
        self.pronunciation_label.setText(pronunciation or "")
        self.input_edit.clear()
        self.result_label.clear()
        
        self.check_button.setEnabled(True)
        self.show_answer_button.setEnabled(True)
        self.next_button.setEnabled(False)
        
        # 自动播放发音
        QTimer.singleShot(500, lambda: self.tts_engine.speak(word))
    
    def play_pronunciation(self):
        """播放发音"""
        if self.current_word:
            word = self.current_word[1]
            self.tts_engine.speak(word)
    
    def check_answer(self):
        """检查答案"""
        if not self.current_word:
            return
        
        user_input = self.input_edit.text().strip().lower()
        word_id, word, pronunciation, meaning, level = self.current_word[:5]
        
        # 判断当前模式
        if self.study_mode == "mixed":
            if self.word_label.text().startswith("📖"):
                current_mode = "spelling"
            else:
                current_mode = "meaning"
        else:
            current_mode = self.study_mode
        
        if current_mode == "spelling":
            correct_answer = word.lower()
            is_correct = user_input == correct_answer
        else:
            correct_answer = meaning
            is_correct = user_input in meaning.lower()
        
        # 更新数据库
        self.db.update_word_progress(word_id, is_correct, current_mode)
        self.word_completed.emit(word_id, is_correct, current_mode)
        
        if is_correct:
            # 正确答案：显示简短提示后直接进入下一个
            self.result_label.setText("✅ 正确！")
            self.result_label.setStyleSheet("""
                QLabel {
                    background-color: #2ecc71;
                    color: white;
                    border-radius: 15px;
                    padding: 15px;
                    margin: 10px 0;
                    font-weight: bold;
                }
            """)
            
            # 1秒后自动进入下一个单词
            QTimer.singleShot(1000, self.next_word)
            
        else:
            # 错误答案：显示正确答案并播放发音
            if current_mode == "spelling":
                self.result_label.setText(f"❌ 错误！正确答案是：{word}")
                # 显示完整单词信息
                self.word_label.setText(f"🔤 {word}")
                self.pronunciation_label.setText(pronunciation or "")
            else:
                self.result_label.setText(f"❌ 错误！正确答案是：{meaning}")
                # 显示完整单词信息
                self.word_label.setText(f"📖 {meaning}")
                self.pronunciation_label.setText(f"🔤 {word}")
            
            self.result_label.setStyleSheet("""
                QLabel {
                    background-color: #e74c3c;
                    color: white;
                    border-radius: 15px;
                    padding: 15px;
                    margin: 10px 0;
                    font-weight: bold;
                }
            """)
            
            # 播放正确答案的发音
            self.tts_engine.speak(word)
            
            # 启用下一个按钮
            self.next_button.setEnabled(True)
        
        # 禁用检查和显示答案按钮
        self.check_button.setEnabled(False)
        self.show_answer_button.setEnabled(False)
    
    def show_answer(self):
        """显示答案"""
        if not self.current_word:
            return
        
        word_id, word, pronunciation, meaning, level = self.current_word[:5]
        
        # 判断当前模式
        if self.study_mode == "mixed":
            if self.word_label.text().startswith("📖"):
                current_mode = "spelling"
                self.result_label.setText(f"💡 答案是：{word}")
                # 显示完整单词信息
                self.word_label.setText(f"🔤 {word}")
                self.pronunciation_label.setText(pronunciation or "")
            else:
                current_mode = "meaning"
                self.result_label.setText(f"💡 答案是：{meaning}")
                # 显示完整单词信息
                self.word_label.setText(f"📖 {meaning}")
                self.pronunciation_label.setText(f"🔤 {word}")
        else:
            if self.study_mode == "spelling":
                self.result_label.setText(f"💡 答案是：{word}")
                # 显示完整单词信息
                self.word_label.setText(f"🔤 {word}")
                self.pronunciation_label.setText(pronunciation or "")
            else:
                self.result_label.setText(f"💡 答案是：{meaning}")
                # 显示完整单词信息
                self.word_label.setText(f"📖 {meaning}")
                self.pronunciation_label.setText(f"🔤 {word}")
            current_mode = self.study_mode
        
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #f39c12;
                color: white;
                border-radius: 15px;
                padding: 15px;
                margin: 10px 0;
                font-weight: bold;
            }
        """)
        
        # 播放单词发音
        self.tts_engine.speak(word)
        
        # 记录为错误
        self.db.update_word_progress(word_id, False, current_mode)
        self.word_completed.emit(word_id, False, current_mode)
        
        self.check_button.setEnabled(False)
        self.show_answer_button.setEnabled(False)
        self.next_button.setEnabled(True)
    
    def next_word(self):
        """下一个单词"""
        self.current_index += 1
        if self.current_index < len(self.current_words):
            word_data = self.current_words[self.current_index]
            self.set_word(word_data)
        else:
            self.finish_study()
    
    def finish_study(self):
        """完成学习"""
        self.word_label.setText("🎉 学习完成！")
        self.pronunciation_label.setText("恭喜您完成了本轮学习！")
        self.input_edit.clear()
        self.result_label.setText("✨ 太棒了！继续保持学习的热情！")
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #2ecc71;
                color: white;
                border-radius: 15px;
                padding: 15px;
                margin: 10px 0;
                font-weight: bold;
            }
        """)
        
        self.start_button.setText("🚀 开始学习")
        self.start_button.setEnabled(True)
        self.check_button.setEnabled(False)
        self.show_answer_button.setEnabled(False)
        self.next_button.setEnabled(False)

class StatisticsWidget(QWidget):
    """统计界面"""
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("📊 学习统计")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #2c3e50; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # 统计卡片容器
        self.stats_container = QWidget()
        self.stats_layout = QGridLayout(self.stats_container)
        self.stats_layout.setSpacing(20)
        
        layout.addWidget(self.stats_container)
        layout.addStretch()
        self.setLayout(layout)
        
        self.update_statistics()
    
    def create_stat_card(self, title, value, color):
        """创建统计卡片"""
        card = QWidget()
        card.setFixedHeight(120)
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {color};
                border-radius: 15px;
                margin: 5px;
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: white;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_label = QLabel(str(value))
        value_label.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        value_label.setStyleSheet("color: white;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        
        return card
    
    def update_statistics(self):
        """更新统计数据"""
        # 清除现有卡片
        for i in reversed(range(self.stats_layout.count())):
            self.stats_layout.itemAt(i).widget().setParent(None)
        
        # 获取统计数据
        stats = self.db.get_user_statistics()
        
        if not stats:
            return
        
        # 创建统计卡片
        cards = [
            ("📚 总单词数", stats['total_words'], "#3498db"),
            ("✅ 已学习", stats['studied_words'], "#2ecc71"),
            ("🏆 已掌握", stats['mastered_words'], "#9b59b6"),
            ("🎯 今日学习", stats['today_studied'], "#e74c3c"),
            ("🎖️ 正确率", f"{stats['accuracy']}%", "#f39c12"),
            ("📈 学习进度", f"{round(stats['mastered_words']/max(stats['total_words'], 1)*100, 1)}%", "#1abc9c")
        ]
        
        for i, (title, value, color) in enumerate(cards):
            card = self.create_stat_card(title, value, color)
            row, col = i // 3, i % 3
            self.stats_layout.addWidget(card, row, col)

class SettingsWidget(QWidget):
    """设置界面"""
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("⚙️ 设置")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #2c3e50; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # 用户信息
        user_group = QGroupBox("👤 用户信息")
        user_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #f8f9fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px 0 10px;
                color: #2c3e50;
            }
        """)
        user_layout = QVBoxLayout()
        
        user_info = self.db.get_user_info()
        if user_info:
            username, email, created_at, last_login = user_info
            user_layout.addWidget(QLabel(f"用户名: {username}"))
            user_layout.addWidget(QLabel(f"邮箱: {email or '未设置'}"))
            user_layout.addWidget(QLabel(f"注册时间: {created_at[:19] if created_at else '未知'}"))
            user_layout.addWidget(QLabel(f"最后登录: {last_login[:19] if last_login else '未知'}"))
        
        user_group.setLayout(user_layout)
        layout.addWidget(user_group)
        
        # 数据管理
        data_group = QGroupBox("📊 数据管理")
        data_group.setStyleSheet(user_group.styleSheet())
        data_layout = QVBoxLayout()
        
        reset_button = QPushButton("🔄 重置学习进度")
        reset_button.clicked.connect(self.reset_progress)
        reset_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        data_layout.addWidget(reset_button)
        
        logout_button = QPushButton("🚪 退出登录")
        logout_button.clicked.connect(self.logout)
        logout_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        data_layout.addWidget(logout_button)
        
        data_group.setLayout(data_layout)
        layout.addWidget(data_group)
        
        # 关于
        about_group = QGroupBox("ℹ️ 关于")
        about_group.setStyleSheet(user_group.styleSheet())
        about_layout = QVBoxLayout()
        
        about_text = QLabel("""
        <h3>单词记忆助手 v2.0</h3>
        <p>一个支持多用户的智能英语单词学习工具</p>
        <p><b>新功能：</b></p>
        <ul>
        <li>🔐 多用户支持</li>
        <li>📊 个人学习统计</li>
        <li>🎯 智能复习算法</li>
        <li>📈 掌握程度跟踪</li>
        </ul>
        <p><b>学习模式：</b></p>
        <ul>
        <li>✏️ 拼写练习</li>
        <li>📖 词义练习</li>
        <li>🎲 混合模式</li>
        </ul>
        """)
        about_text.setWordWrap(True)
        about_text.setStyleSheet("color: #2c3e50; line-height: 1.5;")
        about_layout.addWidget(about_text)
        
        about_group.setLayout(about_layout)
        layout.addWidget(about_group)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def reset_progress(self):
        """重置学习进度"""
        reply = QMessageBox.question(self, "确认重置", 
                                   "确定要重置您的学习进度吗？\n此操作不可撤销！",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            
            # 清空当前用户的学习记录
            cursor.execute('DELETE FROM study_records WHERE user_id = ?', (self.db.current_user_id,))
            cursor.execute('DELETE FROM user_word_progress WHERE user_id = ?', (self.db.current_user_id,))
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "重置完成", "学习进度已重置！")
    
    def logout(self):
        """退出登录"""
        reply = QMessageBox.question(self, "确认退出", 
                                   "确定要退出登录吗？",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.db.current_user_id = None
            QApplication.quit()

class WordMemoryApp(QMainWindow):
    """主应用程序"""
    def __init__(self):
        super().__init__()
        self.db = UserDatabase()
        
        # 显示登录对话框
        login_dialog = LoginDialog(self.db)
        if login_dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit()
        
        self.init_ui()
        self.load_system_state()
    
    def init_ui(self):
        self.setWindowTitle("单词记忆助手 v2.0 - 多用户版")
        
        # 设置默认字体
        font = QFont("Microsoft YaHei", 10)
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        QApplication.setFont(font)
        
        # 从系统状态加载窗口几何信息，如果没有则使用默认值
        saved_geometry = self.db.load_system_state('window_geometry', [100, 100, 1000, 700])
        self.setGeometry(*saved_geometry)
        
        # 设置应用样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
                font-family: "Microsoft YaHei", "SimHei", "Arial Unicode MS", sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #e1e1e1;
                padding: 12px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 3px solid #3498db;
            }
            QTabBar::tab:hover {
                background-color: #d5d5d5;
            }
            QLabel {
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
            }
            QPushButton {
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
            }
            QLineEdit {
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
            }
            QComboBox {
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
            }
        """)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # 学习页面
        self.study_widget = StudyWidget(self.db)
        self.study_widget.word_completed.connect(self.on_word_completed)
        self.tab_widget.addTab(self.study_widget, "📚 学习")
        
        # 统计页面
        self.statistics_widget = StatisticsWidget(self.db)
        self.tab_widget.addTab(self.statistics_widget, "📊 统计")
        
        # 设置页面
        self.settings_widget = SettingsWidget(self.db)
        self.tab_widget.addTab(self.settings_widget, "⚙️ 设置")
        
        self.setCentralWidget(self.tab_widget)
        
        # 从系统状态加载当前标签页
        saved_tab = self.db.load_system_state('current_tab', 0)
        self.tab_widget.setCurrentIndex(saved_tab)
        
        # 设置状态栏
        user_info = self.db.get_user_info()
        if user_info:
            username = user_info[0]
            self.statusBar().showMessage(f"欢迎使用单词记忆助手，{username}！")
            
        # 设置状态栏字体
        self.statusBar().setStyleSheet("""
            QStatusBar {
                font-family: "Microsoft YaHei", "SimHei", sans-serif;
                font-size: 11px;
                color: #2c3e50;
            }
        """)
    
    def load_system_state(self):
        """加载系统状态"""
        try:
            # 加载学习模式设置
            study_mode = self.db.load_system_state('study_mode', '拼写练习')
            if hasattr(self.study_widget, 'mode_combo'):
                index = self.study_widget.mode_combo.findText(study_mode)
                if index >= 0:
                    self.study_widget.mode_combo.setCurrentIndex(index)
            
            # 加载难度级别设置
            difficulty_level = self.db.load_system_state('difficulty_level', '全部')
            if hasattr(self.study_widget, 'level_combo'):
                index = self.study_widget.level_combo.findText(difficulty_level)
                if index >= 0:
                    self.study_widget.level_combo.setCurrentIndex(index)
                    
        except Exception as e:
            print(f"加载系统状态时出错: {e}")
    
    def save_system_state(self):
        """保存系统状态"""
        try:
            # 保存窗口几何信息
            geometry = self.geometry()
            self.db.save_system_state('window_geometry', [geometry.x(), geometry.y(), geometry.width(), geometry.height()])
            
            # 保存当前标签页
            self.db.save_system_state('current_tab', self.tab_widget.currentIndex())
            
            # 保存学习设置
            if hasattr(self.study_widget, 'mode_combo'):
                self.db.save_system_state('study_mode', self.study_widget.mode_combo.currentText())
            
            if hasattr(self.study_widget, 'level_combo'):
                self.db.save_system_state('difficulty_level', self.study_widget.level_combo.currentText())
                
        except Exception as e:
            print(f"保存系统状态时出错: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.save_system_state()
        event.accept()
    
    def on_word_completed(self, word_id, is_correct, study_mode):
        """单词学习完成回调"""
        if is_correct:
            self.statusBar().showMessage("回答正确！继续加油！", 3000)
        else:
            self.statusBar().showMessage("继续努力，熟能生巧！", 3000)
    
    def on_tab_changed(self, index):
        """标签页切换回调"""
        if index == 1:  # 统计页面
            self.statistics_widget.update_statistics()
        
        # 保存当前标签页状态
        self.db.save_system_state('current_tab', index)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("单词记忆助手")
    app.setOrganizationName("WordMemory")
    
    # 设置应用图标
    app.setWindowIcon(QIcon())
    
    try:
        window = WordMemoryApp()
        window.show()
        sys.exit(app.exec())
    except SystemExit:
        pass

if __name__ == "__main__":
    main()