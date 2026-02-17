CREATE TABLE IF NOT EXISTS audit_application (
	  id SERIAL PRIMARY KEY,
	  audit_name VARCHAR(50),
	  audit_status VARCHAR(15),
	  audit_recommendations VARCHAR(200),
	  application_name VARCHAR(20),
	  ai_operator_name VARCHAR(20),
	  ai_operator_url VARCHAR(30),
	  application_access_type VARCHAR(15));


