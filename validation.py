from marshmallow import Schema, fields, validate

class BusinessProblemSchema(Schema):
    """Schema for validating business problem input"""
    problem = fields.Str(
        required=True,
        validate=[
            validate.Length(min=10, max=2000, error="Problem must be between 10 and 2000 characters"),
            validate.Regexp(r'^[a-zA-Z0-9\s\.,!?\-\'\"]+$', error="Problem contains invalid characters")
        ]
    )
    
class ProcessProblemRequestSchema(Schema):
    """Schema for the entire process problem request"""
    business_problem = fields.Nested(BusinessProblemSchema, required=True)
    user_preferences = fields.Dict(missing={})
    
def validate_request_data(schema, data):
    """Utility function to validate request data against a schema"""
    try:
        result = schema.load(data)
        return result, None
    except Exception as e:
        return None, str(e) 