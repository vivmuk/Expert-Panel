import sqlite3
import json
from datetime import datetime
import os

class ReportDatabase:
    def __init__(self, db_path='reports.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                problem_statement TEXT NOT NULL,
                report_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processing_time_seconds REAL,
                status TEXT DEFAULT 'completed'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                user_agent TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_report(self, user_id, problem_statement, report_data, processing_time=None):
        """Save a completed report to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reports (user_id, problem_statement, report_data, processing_time_seconds)
            VALUES (?, ?, ?, ?)
        ''', (user_id, problem_statement, json.dumps(report_data), processing_time))
        
        report_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return report_id
    
    def get_user_reports(self, user_id, limit=10):
        """Get recent reports for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, problem_statement, created_at, processing_time_seconds, status
            FROM reports 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))
        
        reports = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': r[0],
                'problem_statement': r[1][:100] + '...' if len(r[1]) > 100 else r[1],
                'created_at': r[2],
                'processing_time': r[3],
                'status': r[4]
            }
            for r in reports
        ]
    
    def get_report_by_id(self, report_id, user_id=None):
        """Get a specific report by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM reports WHERE id = ?'
        params = (report_id,)
        
        if user_id:
            query += ' AND user_id = ?'
            params = (report_id, user_id)
        
        cursor.execute(query, params)
        report = cursor.fetchone()
        conn.close()
        
        if report:
            return {
                'id': report[0],
                'user_id': report[1],
                'problem_statement': report[2],
                'report_data': json.loads(report[3]),
                'created_at': report[4],
                'processing_time': report[5],
                'status': report[6]
            }
        return None
    
    def get_analytics(self):
        """Get basic analytics about app usage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total reports
        cursor.execute('SELECT COUNT(*) FROM reports')
        total_reports = cursor.fetchone()[0]
        
        # Average processing time
        cursor.execute('SELECT AVG(processing_time_seconds) FROM reports WHERE processing_time_seconds IS NOT NULL')
        avg_processing_time = cursor.fetchone()[0] or 0
        
        # Reports by day (last 7 days)
        cursor.execute('''
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM reports 
            WHERE created_at >= datetime('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        ''')
        daily_reports = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_reports': total_reports,
            'avg_processing_time': round(avg_processing_time, 2),
            'daily_reports': [{'date': d[0], 'count': d[1]} for d in daily_reports]
        } 