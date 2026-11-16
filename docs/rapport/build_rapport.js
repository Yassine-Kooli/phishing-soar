const fs = require('fs');
const D = require(process.argv[2] + '/node_modules/docx');
const S = process.argv[2];
const {Document,Packer,Paragraph,TextRun,ImageRun,Table,TableRow,TableCell,WidthType,ShadingType,AlignmentType,HeadingLevel,LevelFormat,Footer,Header,PageNumber,BorderStyle,PageBreak} = D;
const W = 9638; // text width A4 with 2 cm margins
const pngSize = f => { const b = fs.readFileSync(f); return [b.readUInt32BE(16), b.readUInt32BE(20)]; };
const P = (t, o = {}) => new Paragraph({ spacing: { after: 120, line: 300 }, alignment: o.align || AlignmentType.JUSTIFIED,
  children: [new TextRun({ text: t, bold: o.bold, italics: o.italics, size: o.size || 21, color: o.color })] });
const B = t => new Paragraph({ numbering: { reference: 'bul', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: t, size: 21 })] });
const N = t => new Paragraph({ numbering: { reference: 'num', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: t, size: 21 })] });
const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: false, children: [new TextRun(t)] });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = t => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const CAP = t => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 240 }, children: [new TextRun({ text: t, italics: true, size: 18, color: '555555' })] });
const CODE = lines => lines.map(l => new Paragraph({ shading: { type: ShadingType.CLEAR, fill: 'F2F2F2', color: 'auto' }, spacing: { after: 0 }, indent: { left: 200 },
  children: [new TextRun({ text: l || ' ', font: 'Consolas', size: 17 })] })).concat([new Paragraph({ spacing: { after: 160 }, children: [] })]);
const IMG = (file, maxW = 600) => { const [w, h] = pngSize(file); const k = Math.min(1, maxW / w); return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
  children: [new ImageRun({ type: 'png', data: fs.readFileSync(file), transformation: { width: Math.round(w * k * 0.75), height: Math.round(h * k * 0.75) }, altText: { title: file, description: file, name: file } })] }); };
const cell = (t, w, hdr, fill) => new TableCell({ width: { size: w, type: WidthType.DXA }, shading: hdr ? { type: ShadingType.CLEAR, fill: '1F4E79', color: 'auto' } : (fill ? { type: ShadingType.CLEAR, fill, color: 'auto' } : undefined),
  margins: { top: 60, bottom: 60, left: 90, right: 90 },
  children: String(t).split('\n').map(line => new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: line, bold: hdr, color: hdr ? 'FFFFFF' : undefined, size: 18 })] })) });
const TBL = (headers, rows, widths) => {
  const tot = widths.reduce((a, b) => a + b, 0); const sc = widths.map(x => Math.round(x * W / tot));
  sc[sc.length - 1] += W - sc.reduce((a, b) => a + b, 0);
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: sc,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, sc[i], true)) })]
      .concat(rows.map((r, ri) => new TableRow({ children: r.map((c, i) => cell(c, sc[i], false, ri % 2 ? 'F3F7FB' : null)) }))) });
};
const SP = () => new Paragraph({ spacing: { after: 120 }, children: [] });
const C = S + '/shots/', F = S + '/fig/';
const kids = [];
const fsx = require('fs');
const exists = f => fs.existsSync(f);
const SHOT = (file, cap, maxW = 600) => { const path = exists(C + file) ? C + file : (exists(F + file) ? F + file : null); return path ? [IMG(path, maxW), CAP(cap)] : [P('[Capture à ajouter : ' + file + ']', { italics: true, color: '9C0006' })]; };
// ---------- cover ----------
kids.push(new Paragraph({ spacing: { before: 2400, after: 240 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Projet SOAR 2026–2027', size: 28, color: '1F4E79', bold: true })] }));
kids.push(new Paragraph({ spacing: { after: 360 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Boîte de signalement du phishing', size: 52, bold: true, color: '1F4E79' })] }));
kids.push(new Paragraph({ spacing: { after: 720 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'de l’e-mail à la purge : rapport technique, flux de données et évaluation', size: 28, italics: true })] }));
kids.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: 'Étudiant : Yassine Kooli', size: 24 })] }));
kids.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: 'Enseignant : Dr. Salah Gontara', size: 24 })] }));
kids.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: 'Dépôt : phishing-soar (Git, branche main)', size: 24 })] }));
kids.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: 'Version du rapport : 16 novembre 2026 (mise à jour après l’étape 8)', size: 24 })] }));
kids.push(new Paragraph({ children: [new PageBreak()] }));
kids.push(H1('Sommaire'));
['1. Résumé', '2. Contexte, objectifs et exigences', '3. État d’avancement', '4. Architecture et services utilisés',
 '5. Flux de données de bout en bout', '6. Mise en œuvre pas à pas', '7. Approbation, purge et vérification (étape 8)',
 '8. Démonstration rejouable et résultats', '9. Tests et évaluation', '10. Contrôle humain et politique d’action',
 '11. Difficultés, défauts et limites', '12. Travail restant et conclusion', 'Annexe A. Arborescence du dépôt', 'Annexe B. Interface de l’analyseur', 'Annexe C. Variables de configuration']
  .forEach(t => kids.push(P(t, { align: AlignmentType.LEFT })));
kids.push(new Paragraph({ children: [new PageBreak()] }));
// ---------- 1 ----------
kids.push(H1('1. Résumé'));
kids.push(P('Le projet répond au sujet « Boîte de signalement du phishing : de l’e-mail à la purge ». Un employé transfère un e-mail suspect à une boîte de signalement. Une chaîne automatisée lit ce message sans l’ouvrir sur un poste, calcule un score expliqué, regroupe les signalements d’une même campagne, répond au rapporteur et, pour un phishing confirmé, demande une décision à l’analyste. Après approbation, elle supprime les copies de la campagne dans toutes les boîtes, bloque les domaines en DNS et vérifie que ces deux actions ont réellement pris effet.'));
kids.push(P('La solution est une pile Docker Compose composée de services libres : Mailpit (messagerie), n8n (orchestration, deux workflows), Webdis (verrous), un analyseur FastAPI, un DNS sinkhole CoreDNS, GoPhish (campagne de démonstration) et leurs volumes.'));
kids.push(P('Ce qui fonctionne sur la pile, vérifié par exécution :'));
['lecture automatique de la boîte de signalement toutes les 30 secondes, avec verrou et déduplication ;',
 'analyse sans exécution : authentification, URL défanged, pièces jointes hachées, règles YARA, liens cachés dans les redirections ;',
 'score explicable (chaque point a sa raison) et verdict safe, review ou phishing ;',
 'regroupement des signalements par campagne (similarité de Jaccard) ;',
 'réponse au rapporteur pour un message sain ; alerte analyste avec deux liens signés (approuver, refuser) pour un phishing ;',
 'après approbation : copie en quarantaine de chaque message, suppression dans toutes les boîtes de la campagne, blocage DNS des domaines, vérification par relecture de la boîte et par résolution DNS ;',
 'refus, expiration et rejeu des liens sans effet ; aucune suppression sans décision valide.'].forEach(t => kids.push(B(t)));
kids.push(P('Ce qui n’est pas réalisé : l’intégration de dossiers DFIR-IRIS (étape 7, choix expliqué en section 11), la mesure comparative avec et sans automatisation, et la série complète de répétitions à publier. Les résultats sont donnés pour un jeu de données synthétique, donc optimistes.'));
kids.push(P('Chiffres principaux : 23 tests unitaires réussis ; 83 courriels synthétiques : rappel 0,77 et précision 1,00 au seuil de 40 (contre 0,23 au seuil 60 du guide) ; analyse moyenne de 14 ms par message ; scénario d’approbation de bout en bout en 10 à 30 secondes depuis le signalement, et environ 2 secondes entre le clic de l’analyste et la purge vérifiée.'));
// ---------- 2 ----------
kids.push(H1('2. Contexte, objectifs et exigences'));
kids.push(H2('2.1 Problème'));
kids.push(P('Les employés transfèrent chaque jour des e-mails suspects. Les analystes les ouvrent un par un, avec le risque de manquer un vrai phishing. Quand une campagne est confirmée, les autres destinataires ont déjà reçu le message : il faut le retirer de leurs boîtes.'));
kids.push(H2('2.2 Objectifs visés'));
['Traiter un signalement sans ouvrir l’e-mail sur le poste d’un analyste.', 'Regrouper les signalements d’une même campagne en un seul dossier.', 'Répondre au rapporteur et aux autres destinataires, et purger les copies restantes.'].forEach(t => kids.push(B(t)));
kids.push(H2('2.3 Exigences communes et réponse du projet'));
kids.push(TBL(['Exigence du sujet', 'État', 'Preuve dans le projet'], [
 ['Workflow SOAR complet, de l’événement à la réponse vérifiée', 'Fait', 'Deux workflows couvrent le parcours complet ; la vérification (relecture des boîtes et résolution DNS) est dans le scénario (section 8).'],
 ['Déploiement reproductible (Docker Compose)', 'Fait', 'compose.yaml, Makefile, .env.example, docs/runbook.md ; images épinglées (section 4.2).'],
 ['Contrôle humain, actions réversibles ou tracées', 'Fait', 'Purge seulement après décision signée ; copies en quarantaine avec SHA-256 ; restauration possible (demo/restore.py) ; politique en section 10.'],
 ['Évaluation chiffrée', 'Partiel', 'Matrice de confusion sur 83 courriels et runs de scénario (section 9) ; comparaison avec et sans automatisation non encore mesurée.'],
 ['Sans service payant ni licence obligatoire', 'Fait', 'Tous les composants sont libres ; CIRCL sans clé ; URLhaus optionnel.'],
], [3, 1.2, 5]));
kids.push(SP());
// ---------- 3 ----------
kids.push(H1('3. État d’avancement'));
kids.push(P('Le tableau reprend les étapes de la feuille de route du guide. « Fait » signifie vérifié sur la pile en fonctionnement.'));
kids.push(TBL(['Étape', 'Contenu', 'État', 'Preuve'], [
 ['1–2', 'Pile Docker Compose, analyseur (parsing, défanging, YARA, score)', 'Fait', '23 tests unitaires (section 9.1) ; service sur le port 8000'],
 ['3', 'Intake n8n : sondage, verrou, analyse, marquage lu en fin de traitement', 'Fait', 'Figures 2 et 2a à 2c ; scénario section 8'],
 ['4', 'Réputation : CIRCL (hachage) et URLhaus (clé optionnelle)', 'Fait', 'Nœud « Reputation lookups » ; CIRCL indisponible dans le laboratoire, donc review'],
 ['5', 'Jeu d’essai synthétique (83 courriels) et matrice de confusion', 'Fait (synthétique)', 'eval/results.txt, dataset/README.md'],
 ['6', 'Routage safe / review / phishing, réponse au rapporteur, alertes', 'Fait', 'Scénario section 8 ; corrections de routage section 11'],
 ['7', 'Dossiers DFIR-IRIS par campagne', 'Non réalisé', 'Dossier de campagne tenu dans SQLite ; IRIS prévu comme suite (section 11)'],
 ['8', 'Approbation, purge, blocage, vérification', 'Fait', 'Workflow 02 et endpoints /approvals ; runs approuvé et refusé vérifiés (section 8)'],
 ['9', 'Réponses aux parties, tests de pannes', 'Partiel', 'Avis aux victimes et remerciement au rapporteur ; pannes et liens expirés testés (sections 7 et 9)'],
 ['10', 'Campagne GoPhish de démonstration', 'Fait', 'demo/gophish_setup.py crée la campagne ; page de formation sans capture d’identifiants'],
 ['11', 'Mesures de temps et chiffrage', 'Partiel', 'eval/evaluate.py et eval/runs/ (cinq répétitions) ; comparaison manuelle à rédiger'],
 ['12', 'Démonstration et rapport', 'Fait (ce rapport)', 'Captures et sorties réelles (section 8)'],
], [0.8, 3.6, 1.4, 4.2]));
kids.push(SP());
// ---------- 4 ----------
kids.push(H1('4. Architecture et services utilisés'));
kids.push(H2('4.1 Vue d’ensemble'));
kids.push(P('La figure 1 montre les services et les échanges. Les numéros renvoient à la section 5.'));
kids.push(IMG(F + 'fig-architecture.png', 600));
kids.push(CAP('Figure 1. Architecture de la solution (diagramme réalisé pour ce rapport d’après la configuration du dépôt). La figure ne montre pas encore la boucle de décision de l’analyste ; voir la figure 4.'));
kids.push(H2('4.2 Services de la pile Docker Compose'));
kids.push(TBL(['Service', 'Image et version', 'Rôle dans le projet', 'Ports (hôte / conteneur)'], [
 ['Mailpit', 'axllent/mailpit:v1.27.11', 'Faux serveur de messagerie : boîte reports@corp.local, boîtes des employés, réception SMTP des réponses, alertes et notifications ; API de recherche, de lecture et de suppression.', 'UI 18025 · SMTP 11025 (hôte) / 1025 (interne)'],
 ['n8n', 'docker.n8n.io/n8nio/n8n:2.40.7', 'Orchestration : workflow 01 (intake, analyse, verdict), workflow 02 (webhook de décision de l’analyste), nœuds HTTP, de code et d’envoi d’e-mails.', '5678'],
 ['Webdis', 'nicolas/webdis:0.1.25', 'Redis en HTTP : verrou par signalement (SET NX EX 120) et marque « done ».', '7379'],
 ['analyzer', 'construit depuis python:3.12-slim (FastAPI 0.115.6, uvicorn 0.34.0, yara-python 4.5.1, dnspython 2.7.0, requests 2.32.3)', 'Seul service qui lit les octets des e-mails : analyse, score, campagnes (SQLite), approbations signées, quarantaine, purge, blocage, vérification.', '8000'],
 ['sinkhole', 'coredns/coredns:1.11.1', 'DNS factice : sert /data/blocklist.hosts (rechargé toutes les 3 s), transmet le reste à 1.1.1.1.', '5354/udp (hôte) / 53 ; IP 172.31.50.53'],
 ['GoPhish', 'gophish/gophish:0.12.1', 'Campagne de démonstration sur un domaine .test ; page de formation qui n’enregistre aucun identifiant.', 'admin 13333 · phishing 18081 ; IP 172.31.50.20'],
 ['Volumes', 'volumes Docker et montages', 'n8n_data (workflows), state (campaigns.db, approvals), sinkhole-data (blocklist), quarantine/ (copies brutes par approbation).', '—'],
], [1.3, 2.4, 4.2, 2.2]));
kids.push(SP());
kids.push(P('Les ports sont ceux du fichier .env du laboratoire. Les valeurs par défaut du guide (8025, 1025, 5353, 3333, 8081) sont en conflit avec d’autres services de la machine ; elles restent modifiables par variables (annexe C).'));
kids.push(H2('4.3 Services externes et outils'));
kids.push(TBL(['Service', 'Usage', 'Statut'], [
 ['CIRCL hashlookup', 'SHA-256 de chaque pièce jointe ; 404 = inconnu, autre erreur = indisponible', 'Actif sans clé ; injoignable depuis le laboratoire lors des essais, le verdict passe alors à review.'],
 ['URLhaus (API abuse.ch)', 'Réputation des URL', 'Désactivé sans URLHAUS_AUTH_KEY (non bloquant).'],
 ['Flux local d’indicateurs', 'Domaines malveillants connus, hors ligne (analyzer/ioc/domains.txt)', 'Actif.'],
 ['DFIR-IRIS, TheHive, Shuffle, OTX, VirusTotal', 'Dossiers d’incident, plateforme alternative, renseignement', 'Non intégrés (IRIS est la suite prévue, section 11).'],
], [3.2, 3.6, 2.8]));
kids.push(SP());
kids.push(H2('4.4 Réseau et sécurité du laboratoire'));
kids.push(B('Réseau Docker dédié 172.31.50.0/24 : le DNS factice (172.31.50.53) et GoPhish (172.31.50.20) ont des adresses fixes ; les autres services se joignent par leur nom (mailpit, analyzer, webdis).'));
kids.push(B('Tous les ports publiés sont liés à 127.0.0.1 ; rien n’est exposé sur le réseau de la machine.'));
kids.push(B('n8n n’envoie pas de télémétrie. Les secrets (APPROVAL_SECRET, clés API) vivent dans .env, ignoré par Git.'));
// ---------- 5 ----------
kids.push(H1('5. Flux de données de bout en bout'));
kids.push(H2('5.1 Étapes du flux'));
kids.push(TBL(['N°', 'Composant', 'Entrée', 'Traitement', 'Sortie / effet'], [
 ['①', 'Employé (Mailpit)', 'E-mail suspect reçu', 'Transfert vers reports@corp.local, pièce jointe message/rfc822', 'Message non lu dans la boîte de signalement'],
 ['②', 'n8n, Poll et List reports', 'Horloge, toutes les 30 s', 'GET /api/v1/search?query=to:reports@corp.local is:unread&limit=20', 'Liste des identifiants Mailpit'],
 ['③', 'n8n, One report each et Idempotence', 'Un identifiant', 'POST Webdis SET report-ID/lock NX EX 120', 'Verrou obtenu : suite ; sinon Already done et arrêt'],
 ['④', 'analyzer /analyze/{id}', 'Identifiant Mailpit', 'Lit le .eml brut, extrait le message transféré, défanging, hachage, YARA, authentification, liens de redirection', 'JSON d’analyse (exemple 5.2)'],
 ['⑤', 'n8n, Reputation lookups (Code)', 'URL et SHA-256', 'CIRCL par pièce jointe ; URLhaus si clé', 'Réputation : hits, hachages malveillants, sources indisponibles ou désactivées'],
 ['⑥', 'analyzer /score', 'Analyse et réputation', 'Somme des points (plafond 100), verdict ; une source indisponible empêche safe', 'Score, verdict, raisons'],
 ['⑦', 'n8n, Verdict', 'Verdict', 'Aiguillage : safe / review / phishing', 'safe → réponse ; review ou phishing → campagne'],
 ['⑧a', 'n8n, Reply safe', 'Rapporteur', 'E-mail SMTP via Mailpit', 'Réponse automatique au rapporteur'],
 ['⑧b', 'analyzer /campaign', 'Analyse', 'Jetons : sujet normalisé, domaine expéditeur, domaines des liens, SHA-256 ; Jaccard ≥ 0,5', 'Numéro de campagne et compteur'],
 ['⑨', 'analyzer /approvals (phishing seulement)', 'Campagne', 'Une seule demande ouverte par campagne ; jetons HMAC-SHA256 pour approuver et refuser', 'Demande pending, expiration à 600 s'],
 ['⑩', 'n8n, Notify analyst', 'Demande et liens', 'E-mail à analyst@corp.local : verdict, raisons, URL défanged, deux liens signés', 'Décision attendue ; aucune suppression à ce stade'],
 ['⑪', 'n8n 02, webhook de décision', 'Clic de l’analyste', 'Vérifie le jeton, l’état et l’expiration (POST /approvals/{id}/decide)', 'Refus : rien ne change. Approbation : étape 12'],
 ['⑫', 'analyzer /execute', 'Demande approuvée', 'Copie chaque message de la campagne en quarantaine, puis supprime, puis bloque les domaines', 'Résultat : quarantaine, suppressions, blocages'],
 ['⑬', 'analyzer /verify, n8n 02', 'Résultat', 'Recompte les copies (attendu 0) ; résout les domaines bloqués dans le DNS factice', 'Avis aux victimes, remerciement, compte rendu à l’analyste'],
 ['⑭', 'n8n, Mark done et Mark read', 'Traitement terminé', 'Webdis SET report-ID/done ; Mailpit PUT read=true', 'Signalement lu et clos'],
 ['⚠', 'n8n, DLQ', 'Erreur HTTP ou de nœud', 'Enregistre statut, erreur et horodatage', 'Message resté non lu : repris au sondage suivant'],
], [0.6, 2.2, 2.0, 3.4, 2.8]));
kids.push(SP());
kids.push(H2('5.2 Exemple de données réelles'));
kids.push(P('Extrait de la réponse de POST /analyze/{id} pour le message mail_001.eml du jeu synthétique. Champs non pertinents omis.'));
kids.push(...CODE([
 '{',
 '  "from": "it@paypa1-secure.test",',
 '  "subject": "Verify your account",',
 '  "subject_norm": "verify your account",',
 '  "sender_domain": "paypa1-secure.test",',
 '  "reply_to": "x@mail-help.test",',
 '  "auth": { "spf": "fail", "dkim": "none", "dmarc": "fail" },',
 '  "urls": [{ "defanged": "hxxp://paypa1-secure[.]test/login", "is_ip": false, "punycode": false, "ioc_hit": false }],',
 '  "attachments": [],',
 '  "features": { "auth_fail": true, "reply_to_mismatch": true, "urgency": true, "lookalike_domain": false, ... }',
 '}']));
kids.push(P('Réponse de POST /score avec cette analyse et une réputation vide (URLhaus désactivé). Le seuil de phishing est désormais 40 :'));
kids.push(...CODE([
 '{"score":40,"verdict":"phishing","unavailable":[],',
 ' "reasons":["auth_fail: +20","reply_to_mismatch: +10","urgency: +10"]}']));
kids.push(P('Ce message illustre une limite : sans la règle « domaine de marque » (lookalike_domain, qui ne reconnaît pas paypa1), la somme atteint seulement 40. Le seuil 40 le classe donc en phishing, alors que le seuil 60 l’aurait laissé en review. Ce choix est discuté en section 9.2.'));
kids.push(H2('5.3 Workflows n8n'));
kids.push(IMG(F + 'fig-workflow.png', 430));
kids.push(CAP('Figure 2. Nœuds et branches du workflow 01-phishing-report (diagramme d’après le JSON exporté). Le nœud DLQ reçoit toutes les erreurs ; ses liaisons ne sont pas dessinées.'));
kids.push(P('Captures réelles de l’instance n8n (figures 2a à 2c) :'));
kids.push(IMG(C + '05-n8n-workflow-canvas.png', 600));
kids.push(CAP('Figure 2a. Canevas n8n du workflow 01-phishing-report, état « Published ».'));
kids.push(IMG(C + '06-n8n-executions.png', 600));
kids.push(CAP('Figure 2b. Historique des exécutions du workflow.'));
kids.push(IMG(C + '10-n8n-execution-detail.png', 600));
kids.push(CAP('Figure 2c. Détail d’une exécution : données de chaque nœud.'));
kids.push(TBL(['Workflow', 'Nœud', 'Type', 'Rôle'], [
 ['01', 'Poll, List reports, One report each', 'Déclencheur, HTTP, split', 'Sondage toutes les 30 s des messages non lus'],
 ['01', 'Idempotence, First time, Already done', 'HTTP Webdis, IF, Set', 'Verrou SET NX ; arrêt si déjà traité'],
 ['01', 'Analyze, Reputation lookups, Score', 'HTTP, Code, HTTP', 'Analyse, réputation, verdict'],
 ['01', 'Verdict', 'Switch', 'safe / review / phishing'],
 ['01', 'Reply safe', 'Envoi e-mail', 'Réponse au rapporteur (seulement pour safe)'],
 ['01', 'Campaign, Request approval, Notify analyst', 'HTTP, HTTP, e-mail', 'Campagne, demande signée, alerte avec liens'],
 ['01', 'Mark done, Mark read, DLQ', 'HTTP, HTTP, Set', 'Clôture ; erreurs enregistrées'],
 ['02', 'Approval link (webhook GET)', 'Webhook', 'Reçoit le clic de l’analyste (id, action, token)'],
 ['02', 'Decide, Approved?, Respond refused', 'HTTP, IF, Respond', 'Vérifie la décision ; refus sans action'],
 ['02', 'Execute purge, Verify, Verified?', 'HTTP, HTTP, IF', 'Purge puis vérification'],
 ['02', 'Build notices, Send notices, Collect', 'Code, e-mail, aggregate', 'Avis aux victimes, remerciement, compte rendu'],
 ['02', 'Analyst: rejected / purge failed / verify failed', 'E-mail', 'Comptes rendus d’échec ou de refus'],
 ['02', 'Respond purged / rejected / failed', 'Respond to webhook', 'Page affichée à l’analyste'],
], [1.0, 3.6, 2.4, 3.6]));
kids.push(SP());
// ---------- 6 ----------
kids.push(H1('6. Mise en œuvre pas à pas'));
kids.push(P('Procédure de reproduction sur une machine Linux avec Docker Compose v2, depuis la racine du dépôt. La procédure complète est dans docs/runbook.md ; elle est reprise ici.'));
const steps = [
 ['Cloner le dépôt', ['git clone <url du dépôt> phishing-soar', 'cd phishing-soar']],
 ['Préparer la configuration', ['cp .env.example .env', '# Renseigner dans .env :', '#   APPROVAL_SECRET  : python3 -c "import secrets;print(secrets.token_hex(32))"', '#   GOPHISH_API_KEY  : interface GoPhish (https://localhost:13333), Settings, Show', '#   LAB_RESET=1      : laboratoire de démonstration uniquement', '# Ports déjà utilisés : modifier MAILPIT_UI_PORT, MAILPIT_SMTP_PORT, SINKHOLE_HOST_PORT, GOPHISH_*_PORT']],
 ['Démarrer la pile', ['make up            # docker compose up -d --build', 'docker compose ps     # six services Up']],
 ['Vérifier les services', ['curl -s localhost:8000/blocklist            # {}', 'curl -s localhost:18025/api/v1/info      # Mailpit (port selon .env)', 'curl -s -o /dev/null -w "%{http_code}\\n" localhost:5678/healthz   # 200']],
 ['Créer le compte propriétaire n8n', ['Ouvrir http://localhost:5678 et créer le compte au premier lancement.']],
 ['Créer l’identifiant SMTP « Mailpit SMTP »', ['Dans n8n : Credentials → New → SMTP.', 'Host : mailpit   Port : 1025   SSL/TLS : désactivé', 'Utilisateur et mot de passe quelconques (MP_SMTP_AUTH_ACCEPT_ANY=1 dans compose.yaml).']],
 ['Importer et activer les workflows', ['for f in n8n/workflows/*.json; do', '  docker cp "$f" phish-soar-n8n-1:/tmp/wf.json', '  docker exec phish-soar-n8n-1 n8n import:workflow --input=/tmp/wf.json', 'done', 'docker exec phish-soar-n8n-1 n8n update:workflow --id=phishIntake0001 --active=true', 'docker exec phish-soar-n8n-1 n8n update:workflow --id=approvalResp0002 --active=true', 'docker restart phish-soar-n8n-1']],
 ['Créer la campagne GoPhish', ['python3 demo/gophish_setup.py      # idempotent : réutilise les objets existants']],
 ['Lancer le scénario complet', ['set -a; . ./.env; set +a', 'python3 demo/scenario.py --decision approve   # environ 1 minute : purge, blocage, avis, vérification', 'python3 demo/scenario.py --decision reject    # rien n’est supprimé', 'python3 demo/scenario.py --decision timeout   # 10 minutes : le lien expire, rien n’est supprimé']],
 ['Lancer les tests unitaires', ['docker run --rm -v "$PWD/analyzer:/src" -w /src phish-soar-analyzer sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"']],
 ['Lancer l’évaluation', ['python3 eval/confusion_matrix.py          # matrice sur le jeu de 83 courriels', 'python3 eval/evaluate.py --runs 5        # cinq runs d’approbation puis la matrice']],
 ['Restaurer après une mauvaise décision', ['python3 demo/restore.py <approval_id>           # essai à blanc', 'python3 demo/restore.py <approval_id> --apply   # renvoie les copies, débloque les domaines']],
];
steps.forEach((s, i) => { kids.push(H3('Étape ' + (i + 1) + ' — ' + s[0])); kids.push(...CODE(s[1])); });
// ---------- 7 ----------
kids.push(H1('7. Approbation, purge et vérification (étape 8)'));
kids.push(P('C’est la partie à risque du sujet. Le principe retenu : le programme ne supprime jamais un e-mail sans une décision humaine valide, et il vérifie ensuite que la suppression et le blocage ont bien eu lieu.'));
kids.push(H2('7.1 Déroulé'));
kids.push(...CODE([
 'Analyse → score « phishing » → campagne → POST /approvals  (une demande ouverte par campagne)',
 'Alerte analyste : deux liens signés  ( approve / reject )  valables 600 s',
 'Clic → n8n 02 → POST /approvals/{id}/decide  (jeton HMAC, état pending, non expiré)',
 '   refus    → statut rejected → avis à l’analyste → aucune suppression',
 '   approbation → statut approved → POST /approvals/{id}/execute',
 '       1. recherche des copies de la campagne (Jaccard ≥ 0,5) hors boîtes du service',
 '       2. quarantaine de chaque copie (quarantine/<id>/<msg>.eml, SHA-256) ; si une écriture échoue, rien n’est supprimé',
 '       3. suppression des copies dans les boîtes des destinataires',
 '       4. blocage des domaines du lien et de l’expéditeur (domaines autorisés refusés)',
 '   vérification → GET /approvals/{id}/verify : copies restantes = 0, résolution DNS = 0.0.0.0 (attente de 20 s)',
 '   avis aux victimes, remerciement au rapporteur, compte rendu à l’analyste']));
kids.push(H2('7.2 Garde-fous'));
kids.push(TBL(['Règle', 'Où elle est appliquée', 'Vérification'], [
 ['Aucune suppression sans demande approuvée', 'POST /execute renvoie 409 si le statut n’est pas approved', 'test_execute_refused_without_approval'],
 ['Un lien ne sert qu’une fois', 'Le statut doit être pending ; sinon 409', 'test_decision_can_only_be_used_once ; rejeu refusé en direct'],
 ['Un lien expire après 10 minutes et ne fait rien', 'Contrôle d’expiration ; statut expired', 'test_expired_approval_is_refused_and_nothing_is_purged ; run timeout'],
 ['Pas de lien falsifiable ni échangeable (approuver ↔ refuser)', 'HMAC-SHA256 sur id, action et expiration ; clé dans .env', 'test_forged_or_swapped_token_is_refused'],
 ['Copie avant suppression', 'Écriture en quarantaine d’abord ; échec = arrêt', 'Contrôle SHA-256 dans restore.py'],
 ['Domaines autorisés jamais bloqués', 'is_allowed() dans block() et _block_targets()', 'test_allowlisted_domain_is_refused'],
 ['Une seule décision par campagne', 'Contrôle et insertion dans une même section verrouillée', 'test_second_report_of_same_campaign_reuses_pending_approval'],
 ['Copie du rapporteur conservée', 'MAILBOX_EXCLUDED : reports@, analyst@, soc@', 'Contrôle du run approuvé'],
 ['Liens jamais ouverts', 'L’analyseur lit les octets ; les liens cachés sont extraits, pas suivis', 'test_link_hidden_in_redirect_parameter'],
], [3.2, 3.6, 2.8]));
kids.push(SP());
kids.push(H2('7.3 Décisions de conception'));
['Seuil de phishing à 40 au lieu de 60 (section 9.2) ; une constante (T_PHISH) permet de revenir à 60.', 'Expiration = aucune action : l’analyste reçoit « expired » ; aucun rappel n’est envoyé.', 'Le premier signalement d’une campagne porte la demande ; les autres rapporteurs ne reçoivent pas encore de remerciement (limite connue).', 'Les copies conservées dans reports@ sont des preuves ; elles ne sont jamais supprimées.'].forEach(t => kids.push(B(t)));
// ---------- 8 ----------
kids.push(H1('8. Démonstration rejouable et résultats'));
kids.push(P('Le script demo/scenario.py rejoue le parcours complet sur la pile : réinitialisation, campagne GoPhish, deux employés signalent le même e-mail, lecture de l’alerte analyste pour en extraire les liens signés, clic sur la décision via n8n, puis contrôle des boîtes, de l’analyseur et du DNS. Chaque exécution écrit un JSON dans eval/runs/. Sept exécutions sont enregistrées : cinq approbations (trois échecs de mise au point, puis deux passages complets, 213423 et 214555), un refus et un lien expiré. Les deux dernières exécutions sont celles qui servent de référence.'));
kids.push(H2('8.1 Résultats des exécutions enregistrées (eval/runs)'));
kids.push(TBL(['Exécution', 'Décision', 'Contrôles réussis', 'Résultat', 'Signalement → alerte (s)', 'Clic → purge vérifiée (s)'], [
 ['212947', 'approve', '5 / 9', 'échec', '12,1', '0,4'],
 ['213245', 'approve', '8 / 9', 'échec', '14,1', '1,6'],
 ['213333', 'approve', '7 / 9', 'échec', '26,1', '1,5'],
 ['213423', 'approve', '9 / 9', 'réussi', '6,1', '1,6'],
 ['213437', 'reject', '6 / 6', 'réussi', '22,1', '—'],
 ['213507', 'timeout', '6 / 6', 'réussi', '22,1', '—'],
 ['214555', 'approve', '9 / 9', 'réussi', '4,1', '3,8'],
], [1.4, 1.3, 1.6, 1.3, 2.2, 2.0]));
kids.push(SP());
kids.push(P('Les trois premières exécutions approuvées ont échoué sur des contrôles de bout en bout (un seul avis par campagne, avis aux victimes, remerciement du rapporteur, compte rendu à l’analyste) ; elles correspondent aux itérations de mise au point. La quatrième passe tous les contrôles : copies supprimées (0 restante), domaines résolus en 0.0.0.0, avis envoyés aux victimes, remerciement, compte rendu, message légitime intact. Ces échecs sont conservés dans eval/runs/ pour traçabilité.'));
kids.push(P('Remarque sur le chronométrage : il mesure l’automatisation seule (signalement → alerte, clic → purge → vérification). Le temps de lecture et de décision de l’analyste n’est pas inclus, car un clic scripté n’en a pas.'));
kids.push(H2('8.2 Captures des écrans'));
kids.push(...SHOT('01-mailpit-inbox.png', 'Figure 3. Boîte Mailpit après un scénario : signalements, réponses et alertes analyste.'));
kids.push(...SHOT('02-mailpit-report-forward.png', 'Figure 4. Signalement transféré : l’e-mail suspect est joint en message/rfc822 et n’est jamais ouvert par l’analyste.'));
kids.push(...SHOT('11-mailpit-analyst-decision.png', 'Figure 5. Alerte analyste avec décision demandée et deux liens signés : approuver, refuser.'));
kids.push(...SHOT('03-mailpit-analyst-alert.png', 'Figure 6. Alerte analyste pour un phishing (run précédent) : verdict, score, raisons, URL défanged.'));
kids.push(...SHOT('04-mailpit-reporter-reply.png', 'Figure 7. Réponse automatique au rapporteur pour un message sain (score 0).'));
kids.push(...SHOT('12-mailpit-after-purge.png', 'Figure 8. Boîte d’un destinataire après approbation : la copie de la campagne a disparu ; le message de l’employé reste dans reports@.'));
kids.push(...SHOT('13-mailpit-victim-notice.png', 'Figure 9. Avis envoyé à une victime après purge.'));
kids.push(...SHOT('14-mailpit-analyst-summary.png', 'Figure 10. Compte rendu à l’analyste après exécution : copies supprimées, domaines bloqués, vérification.'));
kids.push(...SHOT('15-n8n-workflow-02.png', 'Figure 11. Canevas du workflow 02-approval-response (état « Published ») : décision, purge, vérification et avis.'));
kids.push(...SHOT('16-n8n-executions-02.png', 'Figure 12. Exécutions du workflow 02 après le clic de l’analyste.'));
kids.push(...SHOT('07-analyzer-swagger.png', 'Figure 13. Interface Swagger de l’analyseur (http://localhost:8000/docs), endpoints de score, de campagne, d’approbation et de blocage.'));
kids.push(...SHOT('08-gophish-admin-login.png', 'Figure 14. Connexion à l’administration GoPhish (campagne créée par l’API ; certificat auto-signé du laboratoire).', 520));
kids.push(H2('8.3 Blocage DNS et vérification'));
kids.push(...SHOT('term-dns.png', 'Figure 15. Test réel : résolution avant blocage (172.31.50.20), après blocage (0.0.0.0), vérification /verify/dns, restauration.', 600));
// ---------- 9 ----------
kids.push(H1('9. Tests et évaluation'));
kids.push(H2('9.1 Tests unitaires'));
kids.push(P('23 tests couvrent le parsing (texte, HTML en base64, forward imbriqué), les URL en adresse IP, les liens dans les redirections, le regroupement de campagnes, le score et les raisons, la règle « une source indisponible n’est jamais safe », la détection YARA, le refus des domaines autorisés, le rejet d’injection de retour à la ligne, l’écriture atomique du fichier de blocage, et les approbations (jeton falsifié ou inversé, lien à usage unique, expiration sans purge, une seule demande par campagne).'));
kids.push(...SHOT('term-tests.png', 'Figure 16. Sortie réelle de pytest : 23 tests réussis (conteneur python:3.12, requirements-dev.txt).', 600));
kids.push(H2('9.2 Évaluation sur le jeu synthétique (83 courriels)'));
kids.push(P('Le jeu contient 83 courriels générés avec une graine fixe : credential phishing, pièces jointes, liens IP, phishing « difficiles » (compte compromis, authentification réussie), messages internes, marketing plein d’urgence, expéditeurs légitimes mal configurés. eval/confusion_matrix.py interroge l’analyseur en direct.'));
kids.push(TBL(['Seuil', 'VP', 'FP', 'VN', 'FN', 'Précision', 'Rappel'], [
 ['25', '34', '0', '39', '10', '1,00', '0,77'],
 ['40 (retenu)', '34', '0', '39', '10', '1,00', '0,77'],
 ['60 (seuil du guide)', '10', '0', '39', '34', '1,00', '0,23'],
 ['75', '10', '0', '39', '34', '1,00', '0,23'],
], [2.6, 1, 1, 1, 1, 1.4, 1.4]));
kids.push(SP());
kids.push(...SHOT('term-eval.png', 'Figure 17. Sortie réelle de eval/confusion_matrix.py sur les 83 courriels (relance pour ce rapport).', 600));
kids.push(P('Lecture : au seuil 60 du guide, le rappel tombe à 0,23 car la plupart des phishings n’atteignent que 40 ou 50 points. Passer à 40 ne crée aucun faux positif sur ce jeu et porte le rappel à 0,77. Les 10 phishings manqués sont des compromis (score 0) et des cas proches de la limite. Limite majeure : le seuil a été choisi sur ce même jeu, qui a été écrit par la même équipe ; le chiffre est donc optimiste. Il faut le confirmer sur des courriels réels (SpamAssassin, corpus de Nazario) avant de le présenter comme une performance.'));
kids.push(P('Temps d’analyse moyen : 14 ms par message dans la relance.'));
kids.push(H2('9.3 Test de panne de l’analyseur'));
kids.push(P('Protocole : arrêt de l’analyseur, signalement d’une facture, attente de 45 s, redémarrage, attente de la reprise. Résultat : pendant la panne, le signalement reste non lu (il n’est pas perdu) ; après redémarrage, il est analysé et l’alerte « [review] campagne #2 » part au sondage suivant. La version actuelle du workflow marque le message lu seulement après succès.'));
// ---------- 10 ----------
kids.push(H1('10. Contrôle humain et politique d’action'));
kids.push(TBL(['Action', 'Mode', 'Réversibilité / trace', 'Vérification après', 'État'], [
 ['Réponse « sain » au rapporteur', 'Automatique', 'Trace dans l’exécution n8n', 'Message visible dans Mailpit', 'Fait'],
 ['Alerte analyste avec liens signés', 'Automatique (information)', 'Trace n8n et e-mail', 'Demande créée dans l’analyseur', 'Fait'],
 ['Purge des copies de la campagne', 'Approuvée par l’analyste', 'Copie SHA-256 en quarantaine ; restauration par demo/restore.py', 'Recherche renvoie 0 copie', 'Fait (runs 213423 et suivants)'],
 ['Blocage DNS des domaines', 'Approuvé par l’analyste', 'Expiration par TTL (3600 s), levée par DELETE', 'dig et /verify/dns renvoient 0.0.0.0', 'Fait'],
 ['Blocage d’un domaine autorisé', 'Interdit', 'Refusé par l’analyseur', '—', 'Fait (test)'],
 ['Création de dossier IRIS', 'Automatique prévu', 'Historique du dossier', 'Identifiant stocké', 'Non réalisé'],
], [2.6, 2.0, 2.8, 1.8, 1.4]));
kids.push(SP());
// ---------- 11 ----------
kids.push(H1('11. Difficultés, défauts et limites'));
kids.push(H2('11.1 Défauts constatés et état de correction'));
kids.push(N('Réponse « sain » envoyée pour un verdict review. Pendant les essais, la facture (review, score 50) a déclenché la réponse « No phishing indicators, score 0 ». Dans le JSON de travail actuel, seule la sortie « safe » mène à « Reply safe » ; review et phishing mènent à la campagne. Ce point n’a pas été rejoué sur la pile après correction : à vérifier avant la démonstration.'));
kids.push(N('Marquage « lu » trop tôt et mauvais traitement de plusieurs signalements. Une version précédente marquait le message lu avant l’analyse (perte possible si l’analyseur tombait) et ne traitait que le premier signalement d’un sondage. Ces deux points sont corrigés dans le JSON de travail (marquage après succès ; nœuds par élément). La version committée dans Git doit être mise à jour.'));
kids.push(N('Erreurs de connexion transitoires dans n8n (EAI_AGAIN vers analyzer) : les nœuds HTTP réessaient trois fois, puis le message reste non lu et la clé expire après 120 s.'));
kids.push(N('n8n s’est relancé spontanément pendant les essais (signal SIGTERM puis redémarrage). Cause non identifiée. Son interface exige une connexion, ce qui a limité les captures.'));
kids.push(H2('11.2 Limites techniques'));
['Mailpit n’est pas Gmail ni Exchange : les API de purge réelles diffèrent, et les copies sont retrouvées par similarité, pas par identifiant de message.', 'Le blocage DNS est en mémoire dans l’analyseur : un redémarrage le vide (le fichier est alors régénéré).', 'CIRCL était injoignable depuis le laboratoire : les pièces jointes donnent alors review. C’est voulu : une source indisponible n’est jamais « propre ».', 'Un signalement qui échoue en continu est repris toutes les 120 s sans nombre maximal de tentatives.', 'Seul le premier rapporteur d’une campagne reçoit le remerciement ; les autres ne sont pas encore remerciés par e-mail.', 'Le jeu de données est synthétique et le seuil 40 a été choisi sur ce jeu : les résultats sont optimistes.'].forEach(t => kids.push(B(t)));
kids.push(H2('11.3 Écarts par rapport au guide'));
['Ports d’hôte modifiés (conflits locaux).', 'Seuil de phishing à 40 au lieu de 60, justifié par le rappel (section 9.2).', 'DFIR-IRIS non intégré : la base de campagnes est en SQLite, l’alerte analyste sert de dossier. IRIS demande sa propre base et environ 4 Go de mémoire, que le laboratoire ne peut pas fournir en plus de la pile.', 'URLhaus sans clé : « désactivé » et non « indisponible », pour que le scénario sain puisse répondre ; choix à assumer.'].forEach(t => kids.push(B(t)));
// ---------- 12 ----------
kids.push(H1('12. Travail restant et conclusion'));
kids.push(TBL(['Priorité', 'Tâche', 'Raison'], [
 ['1', 'Committer le JSON de travail des deux workflows et mettre à jour le README (tableau d’état encore annoncé « non commencé » pour les étapes 7 à 12)', 'Le dépôt doit décrire ce qui tourne'],
 ['2', 'Rejouer le cas review sur la pile et confirmer l’absence de réponse « score 0» au rapporteur', 'Défaut constaté pendant les essais'],
 ['3', 'Publier la série de cinq exécutions de eval/evaluate.py et la comparaison avec une revue manuelle (docs/evaluation.md)', 'Évaluation chiffrée exigée'],
 ['4', 'Tester le seuil sur un jeu réel (courriels publics)', 'Le chiffre 0,77 est optimiste'],
 ['5', 'Étape 7 : dossiers DFIR-IRIS par campagne, si la mémoire le permet', 'Demandé par le sujet, mais hors périmètre actuel'],
 ['6', 'Limiter le nombre de tentatives et remercier tous les rapporteurs', 'Limites connues'],
], [1.1, 5.4, 3.1]));
kids.push(SP());
kids.push(P('La chaîne est opérationnelle de bout en bout : un signalement est lu sans ouverture, analysé, scoré avec des raisons, regroupé, répondu ou soumis à décision. Après une décision approuvée, les copies sont retirées des boîtes, les domaines sont bloqués et la suppression est vérifiée ; un refus ou un lien expiré ne supprime rien. Le projet n’est pas terminé : l’intégration IRIS, la mesure comparative complète et les corrections des défauts listés restent à faire. Les limites sont décrites ici sans les masquer.'));
// ---------- annexes ----------
kids.push(new Paragraph({ children: [new PageBreak()] }));
kids.push(H1('Annexe A. Arborescence du dépôt'));
kids.push(...CODE(['analyzer/            analyseur FastAPI (app.py, Dockerfile, tests/, yara-rules/, ioc/)',
 'compose.yaml          pile Docker Compose',
 'n8n/workflows/       01-phishing-report.json et 02-approval-response.json (sans identifiants)',
 'dns-sinkhole/        Corefile CoreDNS et base.hosts',
 'gophish/             configuration GoPhish',
 'demo/                scenario.py, report.py, send_sample.py, gophish_setup.py, restore.py',
 'dataset/             make_dataset.py, labels.csv, emls/ (83 courriels synthétiques)',
 'eval/                confusion_matrix.py, evaluate.py, results.txt, runs/ (exécutions JSON)',
 'quarantine/          copies brutes avant purge (contenu ignoré par Git)',
 'docs/                architecture.md, runbook.md, rapport/ (ce rapport et ses captures)',
 'Makefile             up, down, test, reset',
 '.env.example         variables et ports, sans secrets']));
kids.push(H1('Annexe B. Interface de l’analyseur'));
kids.push(TBL(['Méthode et chemin', 'Rôle'], [
 ['POST /analyze/{mailpit_id} · POST /analyze-raw', 'Analyse un message Mailpit ou des octets .eml (10 Mo maximum)'],
 ['POST /score', 'Score, verdict et raisons à partir de l’analyse et de la réputation'],
 ['POST /campaign · POST /campaign/{id}/case/{case_id}', 'Rattache un signalement à une campagne ; enregistre un identifiant de dossier'],
 ['POST /approvals · POST /approvals/{id}/decide', 'Crée la demande (phishing seulement) ; enregistre approve ou reject avec jeton HMAC'],
 ['GET /approvals/{id} · GET /approvals/{id}/plan', 'État d’une demande ; prévisualisation des copies à supprimer, sans décision'],
 ['POST /approvals/{id}/execute · GET /approvals/{id}/verify', 'Purge après approbation ; vérification des copies et du DNS'],
 ['POST /quarantine', 'Copies brutes dans quarantine/ avant toute suppression'],
 ['GET · POST /blocklist, DELETE /blocklist/{domaine}', 'Lire, ajouter (TTL 3600 s par défaut, 86400 s max) ou retirer un blocage'],
 ['GET /verify/dns/{domaine}', 'Résolution auprès du DNS factice ; blocked = true si 0.0.0.0'],
 ['POST /lab/reset-approvals', 'Laboratoire seulement (LAB_RESET=1) : expire les demandes ouvertes'],
], [4.2, 5.4]));
kids.push(SP());
kids.push(H1('Annexe C. Variables de configuration'));
kids.push(P('Les valeurs réelles des secrets ne figurent pas dans ce rapport. Le fichier .env est ignoré par Git.'));
kids.push(TBL(['Variable', 'Défaut', 'Usage'], [
 ['MAILPIT_UI_PORT, MAILPIT_SMTP_PORT', '8025, 1025', 'Ports hôte de Mailpit (18025 et 11025 sur le laboratoire)'],
 ['SINKHOLE_HOST_PORT', '5353', 'Port hôte DNS (5354 sur le laboratoire)'],
 ['GOPHISH_ADMIN_PORT, GOPHISH_PHISH_PORT', '3333, 8081', 'Ports hôte GoPhish (13333 et 18081)'],
 ['GOPHISH_API_KEY', 'vide', 'Clé d’API GoPhish pour demo/gophish_setup.py et scenario.py'],
 ['APPROVAL_SECRET', 'vide', 'Clé HMAC des liens d’approbation (obligatoire pour les approbations)'],
 ['APPROVAL_TTL_SECONDS', '600', 'Délai de décision de l’analyste'],
 ['LAB_RESET', '0', '1 = laboratoire de démonstration (expiration des demandes entre deux runs)'],
 ['URLHAUS_AUTH_KEY', 'vide', 'Clé URLhaus ; vide = source désactivée'],
 ['OTX_API_KEY, VIRUSTOTAL_API_KEY, IRIS_API_KEY', 'vide', 'Prévues, non utilisées'],
], [3.4, 1.4, 4.8]));
// ---------- document ----------
const doc = new Document({
  creator: 'Yassine Kooli', title: 'Boîte de signalement du phishing : rapport de projet', description: 'Rapport de projet SOAR',
  styles: {
    default: { document: { run: { font: 'Arial', size: 21 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Arial', size: 32, bold: true, color: '1F4E79' }, paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, keepLines: true, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Arial', size: 26, bold: true, color: '2E75B6' }, paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, keepLines: true, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Arial', size: 22, bold: true, color: '404040' }, paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, keepLines: true, outlineLevel: 2 } },
    ] },
  numbering: { config: [
    { reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: 'num', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] } ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'Projet SOAR : Boîte de signalement du phishing', size: 16, color: '808080' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ['Page ', PageNumber.CURRENT], size: 16, color: '808080' })] })] }) },
    children: kids,
  }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(process.argv[3], buf); console.log('written', buf.length); });
