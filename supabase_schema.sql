BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE tenants (
    id UUID NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    slug VARCHAR(64) NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    UNIQUE (slug)
);

CREATE TABLE routes (
    id UUID NOT NULL, 
    tenant_id UUID, 
    origem VARCHAR(120) NOT NULL, 
    destino VARCHAR(120) NOT NULL, 
    distancia_km FLOAT NOT NULL, 
    produto VARCHAR(60) NOT NULL, 
    corredor VARCHAR(60), 
    piso_antt_r_per_ton FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX ix_routes_od ON routes (origem, destino, produto);

CREATE TABLE raw_diesel_prices (
    id SERIAL NOT NULL, 
    data DATE NOT NULL, 
    uf VARCHAR(2) NOT NULL, 
    cidade VARCHAR(120), 
    preco_medio FLOAT NOT NULL, 
    fonte VARCHAR(60) DEFAULT 'ANP' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_diesel_data_uf_cidade UNIQUE (data, uf, cidade, fonte)
);

CREATE INDEX ix_diesel_data_uf ON raw_diesel_prices (data, uf);

CREATE TABLE predictions (
    id UUID NOT NULL, 
    tenant_id UUID, 
    idempotency_key VARCHAR(128) NOT NULL, 
    origem VARCHAR(120) NOT NULL, 
    destino VARCHAR(120) NOT NULL, 
    produto VARCHAR(60) NOT NULL, 
    data_alvo DATE NOT NULL, 
    carga_ton FLOAT, 
    frete_r_per_ton FLOAT NOT NULL, 
    banda_p10 FLOAT NOT NULL, 
    banda_p90 FLOAT NOT NULL, 
    drivers JSON NOT NULL, 
    model_version VARCHAR(60) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_prediction_idempotency UNIQUE (tenant_id, idempotency_key), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE explanation_cache (
    id SERIAL NOT NULL, 
    prediction_id UUID, 
    prompt_hash VARCHAR(64) NOT NULL, 
    explanation TEXT NOT NULL, 
    source VARCHAR(20) DEFAULT 'llm' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(prediction_id) REFERENCES predictions (id), 
    UNIQUE (prompt_hash)
);

CREATE TABLE audit_events (
    id BIGSERIAL NOT NULL, 
    tenant_id UUID, 
    event_type VARCHAR(80) NOT NULL, 
    entity_id VARCHAR(128), 
    payload JSON NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id)
);

CREATE INDEX ix_audit_type_created ON audit_events (event_type, created_at);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Running upgrade 0001 -> 0002

CREATE TABLE users (
    id UUID NOT NULL, 
    tenant_id UUID NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    hashed_password VARCHAR(255) NOT NULL, 
    role VARCHAR(20) DEFAULT 'viewer' NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
    UNIQUE (email)
);

CREATE INDEX ix_users_tenant ON users (tenant_id);

CREATE INDEX ix_users_email ON users (email);

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

-- Running upgrade 0002 -> 0003

CREATE TABLE alerts (
    id BIGSERIAL NOT NULL, 
    tenant_id UUID NOT NULL, 
    severity VARCHAR(20) NOT NULL, 
    alert_type VARCHAR(40) NOT NULL, 
    entity_id VARCHAR(64), 
    title VARCHAR(200) NOT NULL, 
    body TEXT NOT NULL, 
    meta JSON DEFAULT '{}' NOT NULL, 
    status VARCHAR(20) DEFAULT 'active' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    resolved_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_alerts_tenant_status ON alerts (tenant_id, status);

CREATE INDEX ix_alerts_dedup ON alerts (tenant_id, alert_type, entity_id, status);

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0002';

-- Running upgrade 0003 -> 0004

ALTER TABLE users ADD COLUMN name VARCHAR(120);

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0003';

COMMIT;

