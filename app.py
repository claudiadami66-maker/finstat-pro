from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
from tinydb import TinyDB, Query
from datetime import datetime
import numpy as np
import json
import csv
import io
import os

app = Flask(__name__)
app.secret_key = 'finstat_pro_2025_secret'

# Base de données TinyDB
db = TinyDB('finstat.json')
clients_table = db.table('clients')

# ── Fonctions statistiques ─────────────────────────────────────────
def compute_stats(values):
    if not values:
        return {}
    arr = np.array(values, dtype=float)
    return {
        'n': len(arr),
        'mean': round(float(np.mean(arr)), 2),
        'median': round(float(np.median(arr)), 2),
        'std': round(float(np.std(arr)), 2),
        'min': round(float(np.min(arr)), 2),
        'max': round(float(np.max(arr)), 2),
        'q1': round(float(np.percentile(arr, 25)), 2),
        'q3': round(float(np.percentile(arr, 75)), 2),
        'iqr': round(float(np.percentile(arr, 75) - np.percentile(arr, 25)), 2),
        'variance': round(float(np.var(arr)), 2),
    }

def build_histogram(values, bins=8):
    if not values:
        return []
    arr = np.array(values, dtype=float)
    counts, edges = np.histogram(arr, bins=bins)
    return [
        {
            'label': f"{edges[i]:.0f} - {edges[i+1]:.0f}",
            'count': int(counts[i])
        }
        for i in range(len(counts))
    ]

def get_all_clients():
    return clients_table.all()

# ── Routes ─────────────────────────────────────────────────────────
@app.route('/')
def index():
    total = len(clients_table.all())
    return render_template('index.html', total=total)

@app.route('/saisie', methods=['GET', 'POST'])
def saisie():
    if request.method == 'POST':
        client = {
            'id': int(datetime.utcnow().timestamp() * 1000),
            'nom': request.form['nom'].strip().upper(),
            'prenom': request.form['prenom'].strip().capitalize(),
            'age': int(request.form['age']),
            'type_compte': request.form['type_compte'],
            'solde': float(request.form['solde']),
            'revenu_mensuel': float(request.form['revenu_mensuel']),
            'nb_transactions': int(request.form['nb_transactions']),
            'montant_moyen_transaction': float(request.form['montant_moyen']),
            'a_credit': request.form.get('a_credit') == 'on',
            'date_ajout': datetime.utcnow().strftime('%d/%m/%Y')
        }
        clients_table.insert(client)
        return redirect(url_for('clients'))
    return render_template('saisie.html')

@app.route('/import-csv', methods=['POST'])
def import_csv():
    file = request.files.get('csv_file')
    if not file:
        return redirect(url_for('saisie'))
    stream = io.StringIO(file.stream.read().decode('utf-8'))
    reader = csv.DictReader(stream)
    for row in reader:
        try:
            client = {
                'id': int(datetime.utcnow().timestamp() * 1000),
                'nom': row['nom'].strip().upper(),
                'prenom': row['prenom'].strip().capitalize(),
                'age': int(row['age']),
                'type_compte': row['type_compte'].strip(),
                'solde': float(row['solde']),
                'revenu_mensuel': float(row['revenu_mensuel']),
                'nb_transactions': int(row['nb_transactions']),
                'montant_moyen_transaction': float(row['montant_moyen_transaction']),
                'a_credit': row.get('a_credit', 'false').lower() == 'true',
                'date_ajout': datetime.utcnow().strftime('%d/%m/%Y')
            }
            clients_table.insert(client)
        except Exception:
            continue
    return redirect(url_for('clients'))

@app.route('/clients')
def clients():
    all_clients = clients_table.all()
    all_clients.reverse()
    return render_template('clients.html', clients=all_clients)

@app.route('/delete/<int:client_id>')
def delete(client_id):
    Client = Query()
    clients_table.remove(Client.id == client_id)
    return redirect(url_for('clients'))

@app.route('/analyse')
def analyse():
    clients = clients_table.all()
    if not clients:
        return render_template('analyse.html', empty=True)

    soldes = [c['solde'] for c in clients]
    revenus = [c['revenu_mensuel'] for c in clients]
    transactions = [c['nb_transactions'] for c in clients]
    montants = [c['montant_moyen_transaction'] for c in clients]

    types = {}
    for c in clients:
        types[c['type_compte']] = types.get(c['type_compte'], 0) + 1

    avec_credit = sum(1 for c in clients if c['a_credit'])

    tranches = {'18-25': 0, '26-35': 0, '36-50': 0, '51+': 0}
    for c in clients:
        if c['age'] <= 25: tranches['18-25'] += 1
        elif c['age'] <= 35: tranches['26-35'] += 1
        elif c['age'] <= 50: tranches['36-50'] += 1
        else: tranches['51+'] += 1

    stats = {
        'solde': compute_stats(soldes),
        'revenu': compute_stats(revenus),
        'transactions': compute_stats(transactions),
        'montant': compute_stats(montants),
    }

    histogrammes = {
        'solde': build_histogram(soldes),
        'revenu': build_histogram(revenus),
    }

    return render_template('analyse.html',
        empty=False,
        stats=json.dumps(stats),
        histogrammes=json.dumps(histogrammes),
        types_compte=json.dumps(types),
        tranches_age=json.dumps(tranches),
        avec_credit=avec_credit,
        total=len(clients)
    )

@app.route('/telecharger-modele')
def telecharger_modele():
    header = "nom,prenom,age,type_compte,solde,revenu_mensuel,nb_transactions,montant_moyen_transaction,a_credit\n"
    exemple = "DUPONT,Jean,34,Épargne,250000,150000,12,25000,true\nMARTIN,Sophie,28,Courant,80000,95000,8,15000,false\n"
    content = header + exemple
    return Response(
        content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=modele_finstat.csv'}
    )

@app.route('/api/clients')
def api_clients():
    clients = clients_table.all()
    return jsonify(clients)

if __name__ == '__main__':
    app.run(debug=True)