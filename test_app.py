import unittest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from app import app
from database import ReportDatabase

class TestExpertPanelApp(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Create a temporary database for testing
        self.test_db_fd, self.test_db_path = tempfile.mkstemp()
        self.db = ReportDatabase(self.test_db_path)
        
    def tearDown(self):
        """Clean up after tests"""
        os.close(self.test_db_fd)
        os.unlink(self.test_db_path)
    
    def test_health_check(self):
        """Test the health check endpoint"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode())
        self.assertEqual(data['status'], 'healthy')
    
    def test_test_endpoint(self):
        """Test the test endpoint"""
        response = self.client.post('/test', 
                                  data=json.dumps({'test': 'data'}),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode())
        self.assertTrue(data['success'])
    
    @patch('app.call_venice_api')
    def test_process_problem_success(self, mock_venice_api):
        """Test successful problem processing"""
        # Mock Venice AI responses
        mock_venice_api.side_effect = [
            # Persona generation response
            {
                "experts": [
                    {
                        "name": "Test Expert",
                        "title": "Test Title",
                        "expertise": "Test Expertise",
                        "background": "Test Background",
                        "focus_area": "Test Focus"
                    }
                ]
            },
            # Expert analysis response
            {
                "expert_name": "Test Expert",
                "key_insights": ["Test insight"],
                "opportunities": ["Test opportunity"],
                "risks": ["Test risk"],
                "recommendations": ["Test recommendation"],
                "confidence_level": 8.5,
                "implementation_steps": ["Test step"]
            },
            # Synthesis response
            {
                "executive_summary": "Test summary",
                "key_themes": ["Test theme"],
                "consensus_areas": ["Test consensus"],
                "conflicting_views": ["Test conflict"],
                "blind_spots": ["Test blind spot"],
                "priority_actions": ["Test action"],
                "success_metrics": ["Test metric"]
            }
        ]
        
        request_data = {
            "business_problem": "Test business problem for analysis"
        }
        
        response = self.client.post('/process_problem',
                                  data=json.dumps(request_data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode())
        self.assertTrue(data['success'])
        self.assertIn('personas', data)
        self.assertIn('insights', data)
        self.assertIn('synthesis', data)
    
    def test_process_problem_invalid_input(self):
        """Test problem processing with invalid input"""
        request_data = {
            "business_problem": ""  # Empty problem
        }
        
        response = self.client.post('/process_problem',
                                  data=json.dumps(request_data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
    
    def test_process_problem_no_json(self):
        """Test problem processing without JSON content type"""
        response = self.client.post('/process_problem',
                                  data="not json")
        
        self.assertEqual(response.status_code, 400)
    
    def test_database_operations(self):
        """Test database operations"""
        # Test saving a report
        report_data = {
            "test": "data",
            "personas": [],
            "insights": [],
            "synthesis": {}
        }
        
        report_id = self.db.save_report(
            user_id="test_user",
            problem_statement="Test problem",
            report_data=report_data,
            processing_time=30.5
        )
        
        self.assertIsNotNone(report_id)
        
        # Test retrieving the report
        retrieved_report = self.db.get_report_by_id(report_id, "test_user")
        self.assertIsNotNone(retrieved_report)
        self.assertEqual(retrieved_report['user_id'], "test_user")
        self.assertEqual(retrieved_report['problem_statement'], "Test problem")
        
        # Test getting user reports
        user_reports = self.db.get_user_reports("test_user")
        self.assertEqual(len(user_reports), 1)
        
        # Test analytics
        analytics = self.db.get_analytics()
        self.assertEqual(analytics['total_reports'], 1)
        self.assertEqual(analytics['avg_processing_time'], 30.5)

class TestValidation(unittest.TestCase):
    """Test input validation"""
    
    def test_business_problem_validation(self):
        """Test business problem validation"""
        from validation import BusinessProblemSchema, validate_request_data
        
        schema = BusinessProblemSchema()
        
        # Valid input
        valid_data = {"problem": "This is a valid business problem with enough characters."}
        result, error = validate_request_data(schema, valid_data)
        self.assertIsNone(error)
        self.assertEqual(result['problem'], valid_data['problem'])
        
        # Too short
        short_data = {"problem": "Too short"}
        result, error = validate_request_data(schema, short_data)
        self.assertIsNotNone(error)
        
        # Missing problem
        missing_data = {}
        result, error = validate_request_data(schema, missing_data)
        self.assertIsNotNone(error)

if __name__ == '__main__':
    # Set environment variable for testing
    os.environ['VENICE_API_KEY'] = 'test_key_for_testing'
    
    unittest.main() 