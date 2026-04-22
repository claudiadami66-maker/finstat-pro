from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import numpy as np
import json
import csv
import io

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finstat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'finstat_pro_2025_secret'

db = SQLAlchemy(app)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    type_compte = db.Column(db.String(50), nullable=False)
    solde = db.Column(db.Float, nullable=False)
    revenu_mensuel = db.Column(db.Float, nullable=False)
    nb_transactions = db.Column(db.Integer, nullable=False)
    montant_moyen_transaction = db.Column(db.Float, nullable=False)
    a_credit = db.Column(db.Boolean, default=False)
    date_ajout = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'nom': self.nom,
            'prenom': self.prenom,
            'age': self.age,
            'type_compte': self.type_compte,
            'solde': self.solde,
            'revenu_mensuel': self.revenu_mensuel,
            'nb_transactions': self.nb_transactions,
            'montant_moyen_transaction': self.montant_moyen_transaction,
            'a_credit': self.a_credit,
            'date_ajout': self.date_ajout.strftime('%d/%m/%Y')
        }

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

@app.route('/')
def index():
    total = Client.query.count()
    return render_template('index.html', total=total)

@app.route('/saisie', methods=['GET', 'POST'])
def saisie():
    if request.method == 'POST':
        client = Client(
            nom=request.form['nom'].strip().upper(),
            prenom=request.form['prenom'].strip().capitalize(),
            age=int(request.form['age']),
            type_compte=request.form['type_compte'],
            solde=float(request.form['solde']),
            revenu_mensuel=float(request.form['revenu_mensuel']),
            nb_transactions=int(request.form['nb_transactions']),
            montant_moyen_transaction=float(request.form['montant_moyen']),
            a_credit=request.form.get('a_credit') == 'on'
        )
        db.session.add(client)
        db.session.commit()
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
            client = Client(
                nom=row['nom'].strip().upper(),
                prenom=row['prenom'].strip().capitalize(),
                age=int(row['age']),
                type_compte=row['type_compte'].strip(),
                solde=float(row['solde']),
                revenu_mensuel=float(row['revenu_mensuel']),
                nb_transactions=int(row['nb_transactions']),
                montant_moyen_transaction=float(row['montant_moyen_transaction']),
                a_credit=row.get('a_credit', 'false').lower() == 'true'
            )
            db.session.add(client)
        except Exception:
            continue
    db.session.commit()
    return redirect(url_for('clients'))

@app.route('/clients')
def clients():
    all_clients = Client.query.order_by(Client.date_ajout.desc()).all()
    return render_template('clients.html', clients=all_clients)

@app.route('/delete/<int:id>')
def delete(id):
    client = Client.query.get_or_404(id)
    db.session.delete(client)
    db.session.commit()
    return redirect(url_for('clients'))

@app.route('/analyse')
def analyse():
    clients = Client.query.all()
    if not clients:
        return render_template('analyse.html', empty=True)

    soldes = [c.solde for c in clients]
    revenus = [c.revenu_mensuel for c in clients]
    transactions = [c.nb_transactions for c in clients]
    montants = [c.montant_moyen_transaction for c in clients]

    types = {}
    for c in clients:
        types[c.type_compte] = types.get(c.type_compte, 0) + 1

    avec_credit = sum(1 for c in clients if c.a_credit)

    tranches = {'18-25': 0, '26-35': 0, '36-50': 0, '51+': 0}
    for c in clients:
        if c.age <= 25: tranches['18-25'] += 1
        elif c.age <= 35: tranches['26-35'] += 1
        elif c.age <= 50: tranches['36-50'] += 1
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
    clients = Client.query.all()
    return jsonify([c.to_dict() for c in clients])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)