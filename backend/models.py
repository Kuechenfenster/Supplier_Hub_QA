import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Database URL - defaults to SQLite (use DATABASE_URL env var to override)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///backend/db/supplier_hub.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Internal Users (Company Admin/Staff)
class InternalUser(Base):
    __tablename__ = "internal_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    full_name = Column(String(100), nullable=False)
    invitation_code = Column(String(50), unique=True, nullable=False, index=True)
    invitation_used = Column(Boolean, default=False)
    invitation_expires = Column(DateTime, nullable=False)
    role = Column(String(20), nullable=False, default="viewer")
    department_id = Column(Integer, ForeignKey("departments.id"))
    supervisor_id = Column(Integer, ForeignKey("internal_users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Explicit foreign_keys to avoid ambiguity
    department = relationship("Department", back_populates="users", foreign_keys=[department_id])
    # supervisor is many-to-one (each user has one supervisor)
    # remote_side=[id] tells SQLAlchemy that 'id' is on the parent side
    supervisor = relationship("InternalUser",
                              remote_side=[id],
                              foreign_keys=[supervisor_id],
                              uselist=False,
                              back_populates="subordinates")
    # subordinates is one-to-many (each user can have many subordinates)
    # overlaps="supervisor" tells SQLAlchemy this relationship overlaps with supervisor
    # to avoid the warning about copying the same column
    subordinates = relationship("InternalUser",
                                foreign_keys=[supervisor_id],
                                back_populates="supervisor",
                                overlaps="supervisor")

# Departments
class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    code = Column(String(10), unique=True, nullable=False)
    location = Column(String(100), nullable=True)
    description = Column(Text)
    manager_id = Column(Integer, ForeignKey("internal_users.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    users = relationship("InternalUser", back_populates="department", foreign_keys=[InternalUser.department_id])
    

# Suppliers (extended)
class Supplier(Base):
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    code = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    status = Column(String(20), default="pending")
    assigned_to = Column(Integer, ForeignKey("internal_users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Audit Log
class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("internal_users.id"))
    action = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer)
    old_value = Column(Text)
    new_value = Column(Text)
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
