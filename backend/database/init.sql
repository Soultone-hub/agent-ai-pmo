CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TYPE user_role AS ENUM ('pmo', 'chef_projet', 'direction', 'consultant');
CREATE TYPE project_status AS ENUM ('active', 'archived');
CREATE TYPE doc_type AS ENUM ('rapport', 'cr_reunion', 'planning', 'autre');
CREATE TYPE analysis_type AS ENUM ('document', 'risks', 'copil', 'kpi');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'pmo',
    created_at TIMESTAMP DEFAULT NOW()
);
 
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    status project_status DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    doc_type doc_type DEFAULT 'autre',
    content_text TEXT,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    analysis_type analysis_type NOT NULL,
    result_json JSONB,
    model_used VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);