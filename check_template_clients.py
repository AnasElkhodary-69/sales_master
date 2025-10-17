#!/usr/bin/env python3
"""Check template client_id assignments"""
from models.database import db, EmailTemplate, Client
from app import create_app

app = create_app()
app.app_context().push()

templates = EmailTemplate.query.filter_by(active=True).all()
print(f'Total active templates: {len(templates)}')
print('\nTemplates by client:')
for t in templates:
    print(f'  ID: {t.id}, Name: {t.name}, Client ID: {t.client_id}, Industry: {t.target_industry}')

clients = Client.query.all()
print(f'\n\nTotal clients: {len(clients)}')
for c in clients:
    print(f'  ID: {c.id}, Name: {c.company_name}')
