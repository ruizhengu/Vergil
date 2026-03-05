from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, nullable=False, index=True)
    contract_name = Column(String, nullable=False)
    contract_type = Column(String)  # "erc20", "erc721", "custom"
    solidity_code = Column(Text, nullable=False)
    parameters = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    compilations = relationship("Compilation", back_populates="contract")


class Compilation(Base):
    __tablename__ = "compilations"

    id = Column(String, primary_key=True)
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=True)
    compilation_id = Column(String, index=True)  # from MCP compile_contract
    abi = Column(JSON)
    bytecode = Column(Text)
    success = Column(Boolean, default=False)
    errors = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("Contract", back_populates="compilations")
    deployments = relationship("Deployment", back_populates="compilation")


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(String, primary_key=True)
    compilation_id_ref = Column(String, ForeignKey("compilations.id"), nullable=True)
    transaction_hash = Column(String)
    contract_address = Column(String)
    chain_id = Column(Integer, default=11155111)
    deployer_address = Column(String)
    status = Column(String, default="pending")  # pending, deployed, failed
    gas_used = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    compilation = relationship("Compilation", back_populates="deployments")
