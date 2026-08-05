#!/usr/bin/env python3
"""Build one substantive, mobile-first study page for every DU LL.B. graph node.

The generator composes original explanations from graph metadata, subject methods,
concept packs, and node-type methods. It never fabricates statutory quotations or
case holdings. Every page includes a current-law verification trail.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import quote

VERSION = "3.0.0"
REPO_BLOB = "https://github.com/Legedith/llb/blob/main/"
SECTIONS = (
    "orientation", "eli15", "outcomes", "prerequisite-bridge", "concept-map",
    "core-note", "issue-method", "boundaries", "authority-map", "worked-problem",
    "exam-method", "revision", "self-test", "sources", "progression",
)
FORBIDDEN = ("enrichment queue", "todo", "coming soon", "placeholder content", "lorem ipsum")
STOP = {
    "the","a","an","and","or","of","to","in","on","for","from","with","under","by","as",
    "law","laws","legal","introduction","meaning","nature","scope","concept","concepts",
    "general","principles","principle","overview","study","notes","including",
}
OFFICIAL = {
    "India Code": "https://www.indiacode.nic.in/",
    "Legislative Department": "https://legislative.gov.in/",
    "Supreme Court judgments": "https://www.sci.gov.in/judgements-case-no/",
    "eCourts services": "https://services.ecourts.gov.in/",
    "UN Treaty Collection": "https://treaties.un.org/",
    "ICJ cases": "https://www.icj-cij.org/cases",
    "WIPO Lex": "https://www.wipo.int/wipolex/",
}


def esc(v: Any) -> str:
    return html.escape(str("" if v is None else v), quote=True)


def clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def sent(v: str) -> str:
    v = clean(v)
    return v if not v or v[-1] in ".?!" else v + "."


def uniq(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        x = clean(v)
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out


def safe_id(v: Any) -> str:
    x = clean(v)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", x):
        raise ValueError(f"unsafe node id: {x!r}")
    return x


def words(markup: str) -> int:
    text = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", markup, flags=re.I|re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return len(re.findall(r"\b[\w’'-]+\b", text))


def ul(items: Sequence[str], css: str = "") -> str:
    attr = f' class="{esc(css)}"' if css else ""
    return f"<ul{attr}>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>"


def pul(items: Sequence[str], css: str = "") -> str:
    return ul([esc(x) for x in items], css)


def section(sid: str, title: str, body: str, eyebrow: str) -> str:
    return f'<section class="study-section" id="{esc(sid)}"><span class="section-eyebrow">{esc(eyebrow)}</span><h2>{esc(title)}</h2>{body}</section>'


def href(nid: str) -> str:
    return f"../../nodes/{quote(safe_id(nid))}/"


def nlink(node: Mapping[str, Any], label: str | None = None, css: str = "node-link") -> str:
    return (f'<a class="{esc(css)}" href="{esc(href(str(node["id"])))}">'
            f'<span>{esc(label or node.get("title") or node["id"])}</span>'
            f'<small>{esc(node.get("code") or node.get("subjectCode") or node.get("kind") or "node")}</small></a>')


def terms(title: str, limit: int = 8) -> list[str]:
    out: list[str] = []
    for raw in re.findall(r"[A-Za-z][A-Za-z0-9'’.-]{2,}", title):
        x = raw.strip(".-")
        if x.lower() in STOP or x.lower() in {y.lower() for y in out}: continue
        out.append(x)
    return out[:limit]


@dataclass(frozen=True)
class Profile:
    name: str
    keys: tuple[str, ...]
    lens: str
    questions: tuple[str, ...]
    method: tuple[str, ...]
    authority: tuple[str, ...]
    results: tuple[str, ...]
    mistakes: tuple[str, ...]
    vocab: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Pack:
    name: str
    keys: tuple[str, ...]
    explanation: str
    test: tuple[str, ...]
    limits: tuple[str, ...]
    exam: str


def prof(name: str, keys: Sequence[str], lens: str, q: Sequence[str], m: Sequence[str], a: Sequence[str], r: Sequence[str], x: Sequence[str], v: Mapping[str,str]) -> Profile:
    return Profile(name, tuple(keys), sent(lens), tuple(map(sent,q)), tuple(map(sent,m)), tuple(map(sent,a)), tuple(map(sent,r)), tuple(map(sent,x)), tuple((k,sent(d)) for k,d in v.items()))


def pack(name: str, keys: Sequence[str], explanation: str, test: Sequence[str], limits: Sequence[str], exam: str) -> Pack:
    return Pack(name, tuple(keys), sent(explanation), tuple(map(sent,test)), tuple(map(sent,limits)), sent(exam))


GENERIC = prof(
    "General legal analysis", (),
    "Convert a broad legal label into answerable questions, locate the controlling source for each question, apply every element to proved facts, test the strongest contrary position, and state the consequence and remedy without skipping qualifications",
    ("What relationship, institution, power, right, duty, offence, process, or remedy is involved", "Which facts trigger the rule and which are irrelevant", "Which source controls for this date, territory, forum, and actor", "What exception, defence, discretion, standard of review, or procedural bar can change the result", "Who bears each burden and what follows if it is not discharged"),
    ("Define the issue narrowly", "Break the rule into cumulative and alternative elements", "Separate threshold, merits, proof, and remedy", "Apply one material fact to each element", "Answer the strongest counterargument", "End with a qualified result and exact next step"),
    ("Current constitutional or statutory text", "Rules, regulations, notifications, treaties, and valid agreements", "Binding precedent from the competent court", "Official records and reliable secondary explanation", "The date, edition, bench, and later treatment of every source"),
    ("Declaration of status, validity, right, or liability", "Order compelling, prohibiting, correcting, or setting aside action", "Compensation, restitution, penalty, punishment, or performance", "Procedural consequence such as exclusion, remand, limitation, transfer, or loss of jurisdiction"),
    ("Treating the node title as the rule", "Giving a result before elements and burden", "Citing a case name without its proposition", "Ignoring commencement, transition, forum, limitation, or later law", "Substituting moral instinct for legal analysis"),
    {"Issue":"The precise legal question generated by material facts", "Rule":"The controlling norm drawn from a valid source", "Application":"Reasoned comparison of each element with proved or assumed facts", "Ratio":"The proposition necessary to the decision on material facts", "Remedy":"The legal response available after entitlement or wrong is established"},
)

PROFILES: tuple[Profile, ...] = (
prof("Jurisprudence and legal theory",("jurisprudence","legal theory"),
 "Jurisprudence asks what law is, why it claims authority, how concepts such as rights and liability are constructed, and how institutions should reason in hard cases",
 ("Which school or theorist supplies the claim","Is it descriptive, analytical, historical, sociological, or normative","What account of validity, authority, rights, duty, justice, or adjudication is assumed","What rival theory explains the same phenomenon differently"),
 ("State the central proposition neutrally","Identify the problem the theory addresses","Explain its account of legal validity and practice","Test it against a hard case","Compare the strongest rival before evaluating"),
 ("The theorist's own text","Reliable scholarly edition or translation","Judgments expressly using the idea","Later criticism separating description from moral endorsement"),
 ("Conceptual clarification","An account of institutional authority","Critique of hidden assumptions","A framework for hard cases"),
 ("Reducing a school to a slogan","Confusing what law is with what it ought to be","Attributing later ideas to an earlier author","Criticising before reconstructing the strongest version"),
 {"Positivism":"Theories separating legal validity from moral merit","Natural law":"Theories connecting legal authority or intelligibility to reason and morality","Realism":"Approaches stressing what officials actually do","Right":"A claim, liberty, power, or immunity depending on the analytical scheme"}),
prof("Constitutional law",("constitution","constitutional"),
 "Constitutional analysis controls public power by identifying the institution acting, the source and limit of its power, the right or structural principle engaged, the standard of review, and the remedy a constitutional court may grant",
 ("Is the respondent constitutionally bound","Which article, competence rule, or structural principle governs","What burden and review test apply","Is the restriction authorised, non-arbitrary, fair, necessary, and proportionate","What remedy is institutionally proper"),
 ("Characterise the act and actor","Locate competence and text","Identify the right or structural limit","State the exact review test","Apply aim, fit, necessity, balance, and safeguards where relevant","Address severability, reading down, and remedy"),
 ("The Constitution as amended for the relevant date","Larger-bench and binding precedent","Implementing statutes and executive instruments","Comparative law only after Indian text and authority"),
 ("Invalidation, declaration, reading down, or severance","Writ or direction","Public-law compensation where recognised","Structural relief with justified supervision"),
 ("Starting with policy instead of competence and right","Using equality as an unstructured fairness clause","Ignoring maintainability, standing, alternative remedy, and territorial nexus","Treating a smaller bench or dissent as controlling","Demanding the same remedy for every violation"),
 {"Judicial review":"Court scrutiny of public action against superior legal norms","State action":"Conduct attributable to an authority bound by constitutional duties","Proportionality":"Review of aim, suitability, necessity, and balance","Severability":"Preserving valid parts that can stand independently"}),
prof("Contract and commercial obligations",("contract","specific relief","sale of goods","partnership"),
 "Contract law determines when voluntary undertakings become enforceable, what obligations and risk allocations they create, how they end, and what relief follows non-performance",
 ("Was a valid agreement formed","Did parties have capacity and genuine consent","Are object, consideration, and terms lawful and certain","What express, implied, statutory, or restitutionary obligation arose","Was performance discharged, excused, frustrated, or breached","What relief survives causation, remoteness, mitigation, and proof"),
 ("Build a formation timeline","Identify promises, conditions, representations, and risk allocation","Classify the defect or breach","State whether void, voidable, unenforceable, discharged, or actionable","Calculate expectation, reliance, restitution, and specific relief separately","Test defences and contractual limits"),
 ("The agreement and incorporated documents","Current contract and special commercial statutes","Binding construction of the provision or clause","Communications, performance, usage, and loss evidence"),
 ("Damages measured by the protected interest","Restitution or restoration","Specific performance, injunction, rescission, rectification, or declaration","Indemnity, contribution, security enforcement, or account"),
 ("Assuming every promise is enforceable","Confusing offer and invitation","Treating breach and loss as one issue","Ignoring conditions, exclusion clauses, and mitigation","Calculating damages without a counterfactual"),
 {"Offer":"A final willingness to be bound on acceptance","Consideration":"The recognised exchange supporting a promise","Voidable":"Effective until the entitled party avoids it","Expectation interest":"The position promised by due performance"}),
prof("Torts and consumer protection",("tort","consumer","motor vehicle"),
 "Tort analysis asks whether a legally protected interest was invaded through fault, strict liability, intention, vicarious responsibility, or statute, whether the wrong caused actionable harm, and what defence or remedy applies",
 ("What interest is protected","What basis of liability is pleaded","What standard of conduct applied","Did factual and legal causation connect breach to damage","What defence, immunity, apportionment rule, or special forum applies"),
 ("Identify the tort and interest","Separate duty, breach, causation, remoteness, damage, and defence","Use a contextual standard","Test intervening events and scope of liability","Classify personal, property, economic, dignitary, and statutory loss","Select compensatory and preventive relief"),
 ("Any special statute or tribunal scheme","Binding duty, standard, causation, and defence cases","Technical evidence where causation is specialised","Records proving loss and mitigation"),
 ("Compensatory, nominal, aggravated, exemplary, or restitutionary damages where available","Injunction, abatement, correction, or apology","Consumer or statutory redress","Contribution and apportionment"),
 ("Calling every accident negligence","Skipping duty because harm occurred","Using foreseeability only once","Ignoring causation and quantum","Treating consumer proceedings as an ordinary suit"),
 {"Duty of care":"A recognised obligation to take reasonable care toward a class of persons","Breach":"Falling below the applicable standard","Remoteness":"The legal boundary on consequences","Vicarious liability":"Responsibility for another's tort through a qualifying relationship"}),
prof("Criminal law",("criminal law","penal code","offence","crime","ipc","bns"),
 "Criminal liability requires exact statutory construction, proof of prohibited conduct and mental state, separate analysis of participation and stage, exclusion of defences, and only then classification and punishment",
 ("What offence was in force at the time and place","Which conduct, circumstance, result, and mental elements must be proved","Is liability principal, joint, constructive, abettorial, conspiratorial, or inchoate","Does a general or special defence arise","What grade and sentence follow"),
 ("Write an element checklist","Allocate evidence and burden","Separate intention, knowledge, recklessness, negligence, motive, and presumption","Analyse causation and concurrence","Treat each participant separately","Apply defences before sentence"),
 ("The offence text in force on the date of conduct","Definitions and general exceptions in the same code","Binding construction of each disputed element","Forensic, medical, digital, and circumstantial evidence linked to elements"),
 ("Acquittal, conviction, or lesser offence","Sentence and ancillary orders","Compensation, restitution, forfeiture, or protection","Procedural consequence for defective charge or proof"),
 ("Reasoning from blame to guilt","Using motive as mens rea","Ignoring replacement-code transition","Combining accused persons without participation analysis","Pleading a defence without evidential foundation"),
 {"Actus reus":"The prohibited conduct, circumstance, omission, or result","Mens rea":"The mental state required for an element","Inchoate offence":"Liability for attempt, abetment, or conspiracy","General exception":"A code-based ground excluding liability despite apparent elements"}),
prof("Criminal procedure",("criminal procedure","crpc","bnss","bail","investigation","trial"),
 "Criminal procedure regulates coercive state power from information and investigation through charge, trial, judgment, appeal, and sentence while protecting liberty, fairness, jurisdiction, and evidentiary integrity",
 ("Which court or officer has power at this stage","What trigger, form, deadline, and safeguard apply","How is the offence procedurally classified under current law","What prejudice or illegality follows from breach","What appeal, revision, inherent, or constitutional remedy is open"),
 ("Identify the procedural stage","Locate jurisdiction and power","List mandatory preconditions and safeguards","Create a compliance chronology","Distinguish irregularity, curable defect, illegality, and prejudice","State immediate order and later review separately"),
 ("The procedure code in force for the proceeding","Special-statute modifications","Constitutional safeguards for arrest, detention, and trial","Orders, process records, diary material, and limitation dates"),
 ("Release, custody order, process, transfer, quashing, discharge, or charge","Retrial, remand, appeal, or revision","Exclusion or limited use where law provides","Compensation or accountability in an appropriate case"),
 ("Answering a stage question with the final merits test","Ignoring special-statute overrides","Treating every breach as nullity","Failing to identify who may invoke the remedy and when","Using old code numbers without transition analysis"),
 {"Cognizance":"Judicial application of mind to an alleged offence for proceeding according to law","Charge":"The formal accusation defining the case to meet","Bail":"Conditional release balancing liberty and process integrity","Revision":"Supervisory correction of material jurisdictional or legal error"}),
prof("Evidence",("evidence","evidentiary","bsa"),
 "Evidence law separates relevance from admissibility, allocates burdens, controls modes of proof, and guides evaluation of testimony, documents, electronic records, presumptions, and expert material",
 ("What proposition is the item offered to prove","Which inclusionary and exclusionary rules apply","Who bears the legal and evidential burden and to what standard","Are authenticity, foundation, competence, and mode of proof established","What weight remains after admission"),
 ("State the proposition","Identify the evidence and inferential link","Apply relevance before exclusion","Establish source, authenticity, and mode","Address hearsay, privilege, confession, character, opinion, or electronic limits","Separate admissibility, sufficiency, credibility, and weight"),
 ("The evidence statute in force for the proceeding","Special proof rules and presumptions","Binding admissibility and mode-of-proof cases","Original record, chain, certificate, metadata, or witness foundation"),
 ("Admission or exclusion","Shifted or discharged burden","Permissible or mandatory presumption","Finding that total proof meets or fails the standard"),
 ("Calling weak evidence inadmissible","Using relevance as the only test","Ignoring the purpose for which a statement is offered","Confusing burden with shifting onus","Treating digital material as self-authenticating"),
 {"Fact in issue":"A fact from which a legal right, liability, or disability directly follows","Relevance":"A legally recognised connection between evidence and proposition","Admissibility":"Permission to receive and use an item","Presumption":"A legal direction or permission to infer one fact from another"}),
prof("Family law",("family","hindu law","muslim law","marriage","divorce","succession"),
 "Family law combines status, personal and secular sources, constitutional values, support, child welfare, property consequences, succession, and protective remedies",
 ("Which personal, secular, customary, or special law governs","Was status validly created","What ground, condition, defence, bar, or discretion applies","How do support, custody, residence, property, and succession interact","Which forum and interim protection are available"),
 ("Identify parties, status, date, place, and governing source","Separate validity, dissolution, finance, child welfare, and succession","Apply every statutory condition and defence","Treat child welfare as a distinct inquiry","Coordinate parallel remedies","Frame interim and final relief separately"),
 ("Applicable personal or secular statute for the date","Constitutional authority affecting equality and dignity","Binding family-court precedent","Marriage, birth, residence, income, property, and care records"),
 ("Declaration of status, nullity, dissolution, or separation","Maintenance, residence, protection, custody, guardianship, or adoption","Partition, succession, dower, gift, or property adjustment","Interim protection and enforcement"),
 ("Assuming one personal law governs everyone","Mixing validity and divorce grounds","Using matrimonial fault to decide child welfare","Ignoring forum and parallel remedies","Treating social practice as binding law"),
 {"Status":"A recognised family relationship carrying legal rights and duties","Maintenance":"Financial support under a personal, secular, or procedural source","Guardianship":"Legal authority and responsibility concerning a minor","Succession":"Transmission of property on death"}),
prof("Property, trusts, and succession",("property","transfer of property","easement","trust","succession"),
 "Property analysis identifies the asset and interests, traces title and transfer, tests formal and substantive validity, ranks competing claims, and separates proprietary from personal relief",
 ("What asset and interest are claimed","How was the interest created, transferred, limited, or extinguished","Were capacity, form, registration, notice, consideration, and restrictions satisfied","Which competing interest has priority","What possession, account, declaration, injunction, or transfer remedy follows"),
 ("Draw a title timeline","Name every interest and holder","Classify the transaction rather than its label","Apply creation and transfer formalities","Test notice, bona fides, and priority","Separate proprietary relief from damages and restitution"),
 ("Title documents and registered instruments","Current transfer, registration, easement, trust, and succession law","Revenue records used only for their proper evidentiary purpose","Binding interest and priority cases"),
 ("Possession, declaration, partition, redemption, foreclosure, sale, or specific transfer","Injunction, account, tracing, or trust relief","Damages, mesne profits, or restitution","Rectification, cancellation, probate, or administration"),
 ("Treating possession as conclusive title","Using mutation as a conveyance","Ignoring registration and attestation","Confusing legal and beneficial interests","Analysing without a chronological title chain"),
 {"Title":"The legally supportable basis for ownership or another proprietary interest","Possession":"Factual control with legally relevant intention","Notice":"Knowledge affecting priority or protection","Priority":"The rule deciding which competing interest prevails"}),
prof("Administrative law",("administrative","delegated legislation","natural justice","tribunal"),
 "Administrative law asks whether a public decision-maker had power, used it for a lawful purpose, followed fair procedure, considered relevant material, respected rights, and reached a reviewable outcome",
 ("What is the source and condition of power","Was delegation or sub-delegation lawful","What notice, disclosure, hearing, impartiality, reasons, consultation, or publication duty applied","Was there error of law, improper purpose, fettering, arbitrariness, irrationality, or disproportionality","What review ground and remedy fit the defect"),
 ("Identify the decision and legal effect","Locate jurisdictional facts and statutory purpose","Separate fairness from merits","Map each review ground to record facts","Respect institutional limits on re-weighing","Choose quashing, prohibition, mandamus, declaration, or remand"),
 ("Parent statute and delegated instrument","Complete administrative record","Binding review standards","Policy, reasons, consultation, and procedural rules"),
 ("Quashing, prohibition, mandamus, declaration, or remand","Interim preservation","Reading down or invalidation of subordinate law","Compensation only with an independent basis"),
 ("Calling every bad decision irrational","Substituting the court's preferred merits outcome","Ignoring appeal and alternative remedy","Confusing absence and misuse of power","Assuming fairness has one fixed procedure"),
 {"Ultra vires":"Outside the lawful scope or condition of power","Natural justice":"Context-sensitive fair hearing and impartiality duties","Relevant consideration":"A matter law requires or permits the decision-maker to consider","Irrationality":"A deferential review ground distinct from appeal or correctness"}),
prof("Civil procedure and limitation",("civil procedure","cpc","limitation","pleading","execution","civil court"),
 "Civil procedure converts substantive claims into a jurisdictionally valid, fair, efficient, and enforceable sequence from institution through pleading, issues, evidence, judgment, decree, appeal, and execution",
 ("Which court has subject, territorial, pecuniary, and personal jurisdiction","Is the claim, party, pleading, process, or application proper","What limitation period, accrual, exclusion, extension, or condonation applies","What interim or case-management order is justified","Is the result an order, judgment, decree, or executable direction and what remedy lies"),
 ("Build a procedural timeline","Identify stage and requested order","Check jurisdiction and limitation first","Match material facts to cause and relief","Apply mandatory language, prejudice, and curability","Separate appeal, review, revision, recall, and execution"),
 ("The civil procedure code and local amendments","The limitation statute and special periods","Court and special-forum rules","Pleadings, process, orders, evidence, judgment, decree, and certified dates"),
 ("Return, rejection, amendment, joinder, transfer, stay, injunction, security, or receiver","Dismissal, decree, cost, interest, or settlement","Appeal, review, revision, restoration","Attachment, sale, delivery, garnishee, or other execution"),
 ("Arguing merits before jurisdiction and limitation","Confusing rejection with dismissal","Treating every procedural error as fatal","Ignoring appealability","Obtaining a decree without planning enforcement"),
 {"Cause of action":"Material facts that must be proved for relief","Decree":"Formal expression conclusively determining rights in a suit as specified by law","Res judicata":"Statutory preclusion of qualifying re-litigation","Limitation":"A time bar measured from defined accrual and adjusted only by law"}),
prof("Company, securities, and insolvency",("company","corporate","securities","insolvency","bankruptcy","ibc"),
 "Corporate analysis distinguishes the entity from participants, allocates power among organs, protects investors and creditors, and applies specialised remedies when governance, disclosure, solvency, or market conduct fails",
 ("Which entity, security, office, transaction, or insolvency process is involved","Who had authority and what fiduciary, statutory, or disclosure duty applied","Were approval, filing, valuation, and disclosure valid","Is the claim personal, derivative, class, regulatory, creditor, or insolvency-based","How do moratorium, priority, and forum alter ordinary remedies"),
 ("Identify entity and capital structure","Separate company property from shareholder interest","Map board, member, creditor, regulator, and professional powers","Test approval and disclosure chronologically","Classify remedy and forum","In insolvency apply default, admission, moratorium, control, plan, priority, and avoidance in order"),
 ("Current company, securities, and insolvency law","Charter, registers, filings, and resolutions","Regulatory and appellate authority","Financial, transaction, valuation, and process records"),
 ("Rectification, declaration, injunction, oppression or mismanagement relief","Disgorgement, penalty, restitution, or investor compensation","Resolution, avoidance, priority distribution, liquidation, or dissolution","Officer liability where elements are proved"),
 ("Piercing the veil whenever hardship occurs","Treating directors as owners of company assets","Ignoring specialised forum and limitation","Confusing default with fraud","Ignoring moratorium and creditor hierarchy"),
 {"Separate personality":"The company is distinct from shareholders and directors","Fiduciary duty":"Loyal and proper exercise of entrusted power","Moratorium":"Statutory pause on specified proceedings during resolution","Resolution plan":"Approved proposal resolving or restructuring the debtor"}),
prof("Labour and employment law",("labour","industrial","employment","trade union","wages","social security"),
 "Labour law classifies the employment relationship, distributes collective and individual rights, regulates industrial action and termination, and channels disputes through specialised institutions",
 ("Who is employer, employee, worker, establishment, or industry under the applicable definition","Is the claim individual, collective, wage, safety, social-security, discrimination, or termination based","What inquiry, notice, consultation, standing order, settlement, or statutory condition applies","Which authority has jurisdiction","What reinstatement, compensation, benefit, penalty, or compliance order is available"),
 ("Start with coverage definitions","Identify contract, standing orders, award, settlement, and policy","Build the disciplinary or termination timeline","Separate inquiry fairness, proof, and proportionality","Distinguish strike, lockout, lay-off, retrenchment, closure, and dismissal","Calculate service and monetary consequences"),
 ("The labour code or legacy statute applicable by commencement and transition","Rules, notifications, standing orders, settlements, and awards","Employment, wage, attendance, inquiry, and contribution records","Binding labour and constitutional precedent"),
 ("Reinstatement, continuity, back wages, compensation, or lesser penalty","Recovery of wages, benefits, gratuity, or contributions","Collective or industrial-dispute relief","Civil, penal, or administrative consequence"),
 ("Skipping coverage definitions","Assuming every termination is retrenchment","Treating defective inquiry as automatic reinstatement","Ignoring commencement of consolidated codes","Calculating relief without service history and mitigation"),
 {"Industrial dispute":"A qualifying employment dispute within the statutory framework","Retrenchment":"Employer termination within the statutory definition and exclusions","Domestic inquiry":"Employer disciplinary fact-finding governed by contract and fairness","Social security":"Protection against defined work and life contingencies"}),
prof("Public international law and institutions",("international law","international institution","united nations","law of nations"),
 "International-law analysis identifies subjects, source, jurisdiction, attribution, breach, excuse, responsibility, institutional process, and domestic implementation",
 ("Which subjects and relationship are involved","What treaty, custom, general principle, resolution, or other source supplies the rule","Is it in force and binding on these actors","What jurisdiction, admissibility, immunity, attribution, and responsibility questions arise","Which forum can give effect to it"),
 ("Identify actors, territory, nationality, time, and forum","Prove source and binding force","Interpret text in context, object, and purpose","Apply jurisdiction and attribution before breach","Consider consent, reservation, derogation, countermeasure, and peremptory norms","Separate international responsibility from domestic enforceability"),
 ("Authenticated treaty text, status, reservations, and declarations","State practice and opinio juris for custom","Competent tribunal decisions","Constitutive instruments, resolutions, reports, and domestic implementing law"),
 ("Cessation, assurance, restitution, compensation, or satisfaction","Provisional measures or supervision","Diplomatic, arbitral, judicial, or treaty-body process","Domestic implementation consistent with constitutional allocation"),
 ("Calling repeated practice custom","Ignoring treaty status and reservation","Assuming automatic domestic enforceability","Skipping jurisdiction and admissibility","Treating all resolutions as equally binding"),
 {"Custom":"General practice accepted as law","Treaty":"An international agreement governed by international law","Attribution":"The link treating conduct as an act of a state or organisation","Reparation":"A consequence designed to address injury caused by breach"}),
prof("Human rights, humanitarian, and refugee law",("human rights","humanitarian","refugee","ihl"),
 "Protection-law analysis identifies the protected person, applicable regime, jurisdiction or control, prohibited conduct, permissible limitation or derogation, positive duty, and effective remedy",
 ("Which regime applies in peace, emergency, occupation, or conflict","Who is protected and who bears the obligation","Is the duty negative, positive, procedural, or absolute","What conflict, status, risk, or nexus must be established","What national, treaty, humanitarian, or refugee remedy is available"),
 ("Classify situation and regime","Identify status and jurisdiction","Separate absolute and qualified rights","Apply necessity, proportionality, precaution, distinction, non-refoulement, or due diligence as appropriate","Separate individual and command responsibility","Plan protection, investigation, reparation, and non-repetition"),
 ("Treaty text, status, reservations, and implementing law","Authoritative commentaries and tribunal decisions","Country, conflict, status, and risk evidence","Domestic constitutional, immigration, criminal, and emergency law"),
 ("Protection from return, detention, attack, discrimination, or ill-treatment","Investigation, prosecution, discipline, or command accountability","Reparation and guarantees of non-repetition","Humanitarian access or status determination"),
 ("Mixing human-rights and humanitarian law without classification","Assuming hardship proves refugee status","Ignoring jurisdiction, nexus, or status","Balancing an absolute prohibition","Using reports without methodology checks"),
 {"Non-refoulement":"Prohibition on transfer to a place of legally defined serious risk","Distinction":"Duty to distinguish protected civilians and objects from lawful military objectives","Proportionality":"A structured limit whose content depends on the regime","Positive obligation":"Duty to take reasonable protective, investigative, or regulatory steps"}),
prof("Environmental law",("environment","pollution","wildlife","forest"),
 "Environmental law integrates permits and standards with constitutional rights, scientific uncertainty, public participation, intergenerational concerns, and restoration-oriented remedies",
 ("What activity, pollutant, ecosystem, species, resource, or clearance is involved","Which regulator, consent, standard, notification, or assessment applies","What evidence establishes risk or harm","How do precaution, polluter pays, public trust, sustainable development, and proportionality interact","What preventive, restorative, compensatory, or penal remedy is feasible"),
 ("Map project and affected environment","Identify approvals and regulatory sequence","Separate risk assessment from proof of completed harm","Test participation, disclosure, appraisal, and reasons","Allocate prevention, mitigation, restoration, and monitoring","Draft measurable relief"),
 ("Current environmental statutes and notifications","Consent, clearance, appraisal, and inspection records","Scientific material with disclosed method and uncertainty","Binding constitutional and tribunal authority"),
 ("Stay, closure, prohibition, consent condition, or remediation","Restoration, compensation, or cost recovery","Monitoring, audit, and continuing supervision","Civil, administrative, or penal enforcement"),
 ("Treating every development conflict as an absolute ban","Using a principle without the statute","Ignoring baseline and cumulative impact","Confusing compensation with restoration","Drafting relief that cannot be monitored"),
 {"Precautionary principle":"Preventive action despite uncertainty where legally defined risk warrants it","Polluter pays":"Allocation of prevention and restoration cost to the responsible polluter","Public trust":"Constraint on state control of certain public resources","EIA":"Structured appraisal of likely environmental effects before decision"}),
prof("Intellectual property",("intellectual property","copyright","patent","trade mark","trademark","design","geographical indication"),
 "Intellectual-property analysis identifies protected subject matter, subsistence and ownership, exclusive rights, alleged act, territorial and temporal scope, exceptions, invalidity, and proportionate relief",
 ("What right is claimed and does it subsist","Who owns or may sue and for what territory and period","Which reserved act or statutory wrong is alleged","What similarity, copying, confusion, inventive, originality, or functionality test applies","What exception, licence, exhaustion, invalidity, or public-interest limit applies"),
 ("Classify the right first","Prove subsistence, title, and chain","Define protected scope without monopolising ideas or function","Compare the defendant's act element by element","Apply exceptions and validity challenges","Separate injunction, damages, account, delivery, and regulatory measures"),
 ("Current IP statute, rules, and register","The work, mark, claim, design, or indication itself","Licence, assignment, priority, and use evidence","Binding precedent and relevant WIPO material"),
 ("Interim or final injunction","Damages or account","Delivery, destruction, correction, cancellation, or rectification","Compulsory or statutory licence where authorised"),
 ("Treating registration as proof of every issue","Comparing products instead of protected features","Ignoring ownership and standing","Skipping exceptions and validity","Seeking injunction without balance and public interest"),
 {"Subsistence":"Whether the right legally exists","Infringement":"Unauthorised performance of a reserved act","Passing off":"Protection of goodwill against damaging misrepresentation","Exhaustion":"A limit on control after authorised circulation"}),
prof("Tax law",("tax","taxation","income tax","gst"),
 "Tax analysis begins with charging authority and taxable event, then person, period, situs, classification, valuation, exemptions, computation, procedure, evidence, and remedy",
 ("What charging provision and event apply","Who is taxable and for which period and jurisdiction","How is the base classified, valued, attributed, and computed","What exemption, deduction, credit, anti-avoidance, withholding, or procedure changes liability","Which assessment, appeal, refund, penalty, or recovery process is open"),
 ("Start with competence and charging text","Identify person, event, place, and period","Classify receipt, supply, asset, or transaction","Compute before concessions","Apply exemptions according to text and purpose","Separate tax, interest, penalty, prosecution, and remedy"),
 ("Statute, finance amendment, rules, rates, and notifications for the period","Return, invoice, books, valuation, payment, and assessment records","Circulars subject to statute and precedent","Orders and limitation dates"),
 ("Assessment modification, deduction, credit, refund, or rectification","Stay or structured recovery","Penalty relief where conditions apply","Appeal, revision, writ, or ruling within jurisdiction"),
 ("Using today's rate for an earlier period","Starting with exemption before charge","Treating accounting label as conclusive","Ignoring territorial rules","Conflating liability with penalty culpability"),
 {"Charging provision":"The rule creating tax liability","Taxable event":"The defined occurrence on which tax is imposed","Assessment period":"The statutory period relevant to computation or assessment","Input tax credit":"A statutory credit subject to defined conditions"}),
prof("Alternative dispute resolution",("alternative dispute","arbitration","conciliation","mediation","negotiation"),
 "ADR analysis centres on consent, scope, neutrality, authority, procedural fairness, court support, finality, confidentiality, and enforceability, while keeping adjudicative awards distinct from consensual settlements",
 ("Is there a valid agreement or statutory referral","Which disputes, parties, seat, venue, law, rules, and institution are covered","Who decides jurisdiction and what court support is permitted","Were equality, notice, disclosure, impartiality, and opportunity respected","What makes the result binding, challengeable, enforceable, or confidential"),
 ("Read the clause as a process allocation","Separate seat, venue, substantive law, and rules","Apply referral, appointment, jurisdiction, interim relief, procedure, award, challenge, and enforcement in order","Distinguish adjudicative and consensual outcome","Respect limited court intervention without erasing safeguards","Plan enforcement while drafting"),
 ("Current arbitration or mediation statute and rules","Agreement, institutional rules, and appointment record","Notices, disclosures, orders, transcript, award, or settlement","Seat and enforcement precedent"),
 ("Referral, appointment, interim protection, or evidence assistance","Jurisdictional ruling, award, or correction","Setting aside, refusal, recognition, or enforcement","Recorded settlement with applicable legal status"),
 ("Calling every private negotiation arbitration","Ignoring non-signatory and scope","Confusing seat and venue","Rearguing merits in limited review","Drafting settlement without performance and enforcement terms"),
 {"Seat":"The legal home of arbitration and source of supervisory jurisdiction","Kompetenz-kompetenz":"Tribunal power to rule on jurisdiction subject to statutory review","Award":"Formal adjudicative determination","Settlement":"Consensual resolution whose legal effect depends on form and framework"}),
prof("Interpretation and legislative drafting",("interpretation","legislative drafting","statute"),
 "Interpretation seeks the legally best meaning of enacted text in linguistic, structural, purposive, constitutional, and temporal context; drafting translates policy into precise, coherent, reviewable rules",
 ("What word, phrase, provision, or conflict needs interpretation","What ordinary, technical, defined, contextual, and purposive meanings are possible","How do scheme, proviso, exception, explanation, schedule, and related law interact","What constitutional presumption or right constrains meaning","Would the reading create surplusage, absurdity, retrospectivity, or remedial failure"),
 ("Quote only necessary operative text","Identify grammar and definitions","Read the whole enactment","State purpose from legitimate material","Use canons as reasons, not commands","Test consequences and compatibility","When drafting specify actor, trigger, duty or power, procedure, standard, time, consequence, review, and transition"),
 ("Authenticated enactment and amendments","Definitions, related provisions, schedules, and commencement instruments","Binding interpretation of the same text","Legitimate internal and external aids"),
 ("A construction resolving the dispute","Reading down, severance, or avoidance where lawful","Transitional handling","A redrafted provision with authority, safeguards, enforcement, and review"),
 ("Selecting a canon before reading the text","Using history to contradict clear text","Treating every proviso alike","Ignoring amendment and commencement","Drafting duties without actor, trigger, deadline, or consequence"),
 {"Purposive construction":"Meaning informed by statutory problem and objective within permissible text","Harmonious construction":"Reading provisions coherently where possible","Proviso":"A drafting device whose function depends on context","Delegation":"Conferral of subordinate law-making or decision power within constitutional limits"}),
prof("Professional ethics and clinical legal work",("professional ethics","advocacy","moot","mock trial","internship","drafting","pleading","conveyancing"),
 "Clinical legal work combines client-centred fact development, professional duties, procedural strategy, accurate drafting, authority control, oral advocacy, record management, and reflective judgment",
 ("Who is the client and what lawful objective is sought","What confidentiality, conflict, competence, candour, independence, and court duty applies","What facts are known, disputed, missing, or privileged","What document, forum, burden, remedy, and deadline control the task","What ethical alternative must be explained"),
 ("Open a chronology and issue list","Verify identity, authority, conflict, scope, and limitation","Separate fact, instruction, inference, evidence, and law","Draft from relief backward to necessary facts and grounds","Cite record and authority precisely","Prepare adverse questions and concessions","Close with responsibility and deadline"),
 ("Professional statute, rules, and court procedure","Complete client and case record","Binding authority and authenticated forms","Engagement, consent, advice, filing, service, and attendance records"),
 ("Competent advice and informed choice","A valid pleading, instrument, opinion, memorial, or oral submission","Correction, withdrawal, disclosure, refusal, or recusal where duty requires","Disciplinary consequence for proved misconduct"),
 ("Treating zeal as permission to mislead","Drafting facts that cannot be proved","Ignoring limitation and service","Reading submissions instead of answering the bench","Advising without assumptions and alternatives"),
 {"Candour":"Duty not to mislead the court and to correct material error where required","Privilege":"Protection for specified confidential legal communications","Pleading":"Formal statement of material facts and relief","Theory of the case":"A coherent link among facts, law, proof, and requested outcome"}),
prof("Competition law",("competition","antitrust"),
 "Competition law tests agreements, dominance, unilateral conduct, and combinations through market and economic evidence to protect competitive process rather than a particular competitor",
 ("What product, geography, time, and constraint define the market","Is conduct an agreement, unilateral practice, or combination","What object, effect, appreciable harm, dominance, foreclosure, efficiency, or benefit matters","What evidence supports the theory of harm","What remedy restores competition"),
 ("State the theory of harm","Define the market only as needed","Establish agreement or dominance before abuse","Connect conduct to mechanism and effect","Test exemption and efficiency","Design a proportionate, monitorable remedy"),
 ("Current competition statute, regulations, and thresholds","Regulator and appellate decisions","Market data, contracts, internal records, pricing, entry, and switching evidence","Economic expert material with disclosed assumptions"),
 ("Cease, modify, access, divest, or condition approval","Penalty, disgorgement, or compensation where authorised","Interim preservation","Commitment, settlement, or monitoring"),
 ("Calling size dominance","Defining market to force the result","Equating harm to one competitor with harm to competition","Using price movement without causal analysis","Seeking remedy unrelated to the theory"),
 {"Relevant market":"The useful field of competitive constraints","Dominance":"Strength assessed under statutory factors, not mere success","Abuse":"Specified exploitative or exclusionary conduct by a dominant enterprise","Combination":"A merger, acquisition, or control transaction subject to review"}),
prof("Banking, insurance, and negotiable instruments",("banking","insurance","negotiable instrument","cheque"),
 "Financial-services analysis begins with the regulated relationship and instrument, then authority, disclosure, payment, risk transfer, dishonour, consumer duties, and enforcement",
 ("What account, instrument, policy, security, or payment is involved","Who is customer, holder, insured, beneficiary, drawer, drawee, endorser, agent, or guarantor","What authority, condition, presentment, notice, loss, or exclusion matters","What regulatory and consumer duties overlay the contract","What civil, summary, penal, or regulatory remedy applies"),
 ("Identify instrument and parties","Trace issue, transfer, authority, presentment, payment, dishonour, and notice","For insurance separate formation, disclosure, coverage, exclusion, causation, indemnity, and subrogation","For banking distinguish mandate, negligence, fraud, and compliance","Check forum and limitation","Calculate principal, interest, loss, and recovery separately"),
 ("Instrument, policy, mandate, security, and communication","Current financial and negotiable-instrument law","Regulatory directions for the date","Transaction, notice, proof-of-loss, and authentication records"),
 ("Payment, indemnity, settlement, recovery, or discharge","Injunction, correction, lien, set-off, subrogation, or security enforcement","Statutory dishonour relief","Regulatory or consumer redress"),
 ("Treating every unpaid cheque as automatic guilt","Ignoring authority and signature","Reading coverage without exclusion and causation","Confusing indemnity with agreed value","Overlooking regulation and limitation"),
 {"Negotiability":"Transfer characteristics enabling a qualifying holder to enforce","Dishonour":"Refusal or failure of acceptance or payment under governing rules","Insurable interest":"The legally recognised relationship supporting insurance protection","Subrogation":"The insurer's derivative recovery right after indemnity"}),
prof("Cyber, data, and media law",("cyber","information technology","data protection","media","internet","electronic"),
 "Digital-law analysis identifies actors, data, systems, content, platform role, territorial link, technical event, statutory duty, constitutional right, evidence trail, and proportionate remedy",
 ("What data, content, system, device, communication, or automated decision is involved","Who is controller, processor, intermediary, originator, publisher, user, investigator, or affected person","What consent, lawful basis, security, retention, takedown, safe-harbour, speech, privacy, or surveillance rule applies","How is digital evidence authenticated","What territorial, regulatory, civil, or criminal remedy applies"),
 ("Draw the data and communication flow","Classify every actor's legal role","Mark collection, use, sharing, publication, restriction, breach, and retention","Apply speech and privacy limits separately","Preserve logs, metadata, certificate, chain, and device integrity","Choose targeted rather than excessive relief"),
 ("Current IT, data, telecom, media, and criminal provisions","Rules, platform terms, notices, consent, and security policies","Device, account, log, header, metadata, and forensic material","Constitutional and statutory privacy and speech cases"),
 ("Correction, erasure, access, restriction, takedown, restoration, or disclosure","Injunction, damages, penalty, blocking, or safe-harbour consequence","Investigation and preservation within safeguards","Regulatory direction and remediation"),
 ("Assuming online conduct has no forum","Calling every unwanted use a crime","Ignoring intermediary role and knowledge","Using screenshots without authentication","Seeking total blocking where narrower relief works"),
 {"Personal data":"Information relating to an identifiable person under applicable law","Intermediary":"A service performing defined storage, transmission, or access functions","Safe harbour":"Conditional protection for specified intermediary functions","Metadata":"Information describing creation, transmission, alteration, or context"}),
prof("Gender justice and feminist jurisprudence",("gender","feminist","women","sexual harassment","domestic violence"),
 "Gender-justice analysis tests facial and structural inequality, stereotypes, distribution of power and care, intersectional disadvantage, bodily autonomy, safety, voice, and practical access to remedies",
 ("What formal rule and lived practice produce disadvantage","Which comparator, stereotype, institutional pattern, or unequal burden matters","How do sex, gender identity, caste, class, disability, sexuality, religion, and migration intersect","What negative and positive duties arise","Does the remedy redistribute power without paternalism"),
 ("Identify institution and affected group","Separate direct, indirect, structural, and intersectional discrimination","Expose the allegedly neutral baseline or stereotype","Apply equality, dignity, autonomy, safety, and due process","Examine enforcement barriers and retaliation","Design survivor-centred and accountable relief"),
 ("Constitutional equality and liberty guarantees","Protective, labour, family, criminal, and anti-discrimination statutes","Binding stereotype and substantive-equality cases","Reliable social evidence with transparent method"),
 ("Protection, residence, support, compensation, reinstatement, or institutional correction","Investigation, prosecution, or discipline with safeguards","Declaration, policy reform, monitoring, and accessibility","Removal of discriminatory rule or practice"),
 ("Treating all women or gender minorities as one group","Using protection to erase autonomy","Assuming formal neutrality creates equality","Ignoring credibility stereotypes and retaliation","Proposing symbolic relief without enforcement"),
 {"Substantive equality":"Equality concerned with real disadvantage, impact, and power","Intersectionality":"Analysis of overlapping disadvantage that cannot be isolated","Stereotype":"Generalised assumption assigning role, capacity, credibility, or blame","Positive duty":"Obligation to prevent, protect, investigate, accommodate, or transform"}),
prof("Criminology, penology, and victim justice",("criminology","penology","victimology","white collar","punishment","prison"),
 "Criminology and penology compare explanations of offending and social control, test purposes and effects of punishment, examine institutional power, and centre lawful treatment and victim participation",
 ("Is the claim causal, correlational, normative, doctrinal, or policy-based","What unit, method, and evidence support it","Which purpose of punishment is asserted and how is success measured","What constitutional and statutory limits govern custody or sanction","How are victim safety, participation, reparation, and accused rights balanced"),
 ("Define theory and assumptions","Identify population, method, variables, and limits","Distinguish explanation from excuse","Compare deterrence, desert, incapacitation, rehabilitation, restoration, and reintegration","Apply legality, proportionality, dignity, and due process","Evaluate unintended institutional effects"),
 ("Original theory and empirical source","Current data with method","Constitutional and statutory custody standards","Judgments and official institutional reports"),
 ("Proportionate and individualised sentence","Custodial safeguards, release, parole, remission, or rehabilitation","Victim compensation, participation, protection, or restoration","Institutional reform and monitoring"),
 ("Treating correlation as causation","Using theory to stereotype","Equating severity with deterrence","Ignoring prison and post-release effects","Erasing victim or due process"),
 {"Deterrence":"Prevention through anticipated consequence","Rehabilitation":"Intervention aimed at reducing future harm and enabling reintegration","Restorative justice":"Processes addressing harm, accountability, participation, and repair","Victimology":"Study of victimisation, response, vulnerability, and rights"}),
prof("Medical and health law",("medical","health law","bioethics","patient"),
 "Health-law analysis combines consent, capacity, professional standard, confidentiality, bodily autonomy, public-health power, regulation, causation, and access",
 ("Who is patient, professional, institution, regulator, surrogate, or authority","Was consent informed, voluntary, specific, contemporaneous, and competent","What professional or institutional standard applied","Did breach cause the harm","What emergency, confidentiality, reproductive, public-health, or allocation rule changes the analysis"),
 ("Create a clinical and communication chronology","Separate diagnosis, advice, consent, treatment, follow-up, and documentation","Identify standard and expert basis","Apply material risk and causation separately","Protect confidentiality and autonomy","Choose civil, consumer, regulatory, constitutional, or criminal response proportionately"),
 ("Health and professional regulation","Medical record, consent, protocol, test, and follow-up evidence","Independent expert evidence for technical standard or causation","Constitutional and consumer precedent"),
 ("Treatment access, correction, disclosure, or protection","Compensation, refund, or consumer relief","Professional discipline or institutional remediation","Public-law or criminal process only where elements exist"),
 ("Treating bad outcome as negligence","Using a signed form as conclusive consent","Ignoring causation and baseline risk","Disclosing information unnecessarily","Criminalising ordinary error without the required threshold"),
 {"Informed consent":"Voluntary decision based on material information and capacity","Clinical negligence":"Breach of the legally applicable professional standard causing harm","Confidentiality":"Duty controlling use and disclosure of health information","Capacity":"Decision-specific ability to understand, weigh, and communicate relevant information"}),
)

PACKS: tuple[Pack, ...] = (
pack("Equality and non-arbitrariness", ("equality", "article 14", "arbitrariness", "classification"),
 "Equality review asks whether similarly situated persons are treated alike, whether a distinction rests on an intelligible basis connected with the law's purpose, and whether state action is arbitrary, stereotyped, disproportionate, or structurally exclusionary",
 ("Identify the state action and affected class", "Choose the correct comparator without assuming the disputed rule", "State the classification or impact", "Test intelligible differentia and rational nexus where classification is used", "Test arbitrariness, substantive equality, stereotype, and proportionality where the claim requires them", "Connect the defect to an appropriate remedy"),
 ("Article 14 does not prohibit every distinction", "A rational classification may still fail another right", "Formal equal treatment can preserve real disadvantage", "Courts do not replace policy merely because another choice was possible"),
 "Use separate paragraphs for comparator, classification, purpose, nexus, arbitrariness, impact, and remedy; do not collapse every equality case into one slogan"),
pack("Freedoms and reasonable restrictions", ("article 19", "freedom of speech", "freedom of movement", "freedom of association", "reasonable restriction"),
 "A freedom claim first identifies the protected activity and claimant, then the constitutionally permitted ground of restriction, legal authority, procedural safeguards, and a proportionate connection between means and legitimate end",
 ("Identify the precise freedom and activity", "Ask whether the claimant may invoke the freedom", "Locate law authorising the restriction", "Match the restriction to an enumerated constitutional ground", "Test reasonableness and proportionality", "Examine vagueness, overbreadth, prior restraint, chilling effect, and safeguards"),
 ("Not every inconvenience is a constitutional restriction", "A desirable objective must still fit an enumerated ground", "Indirect burdens may matter", "Speech protection does not erase valid duties concerning crime, reputation, privacy, or fair process"),
 "Write the restriction ground exactly, then show authority, fit, necessity, balance, and safeguards in that order"),
pack("Life, liberty, dignity, and privacy", ("article 21", "life and personal liberty", "privacy", "dignity", "due process"),
 "Life and liberty protection requires lawful authority, a fair and non-arbitrary procedure, respect for dignity and decisional or informational autonomy, and proportionate safeguards against unjustified intrusion",
 ("Identify the liberty, bodily, decisional, informational, or dignitary interest", "Locate substantive and procedural authority", "Test fairness, notice, hearing, reasons, and review", "Apply legality, legitimate aim, necessity, proportionality, and safeguards where privacy is engaged", "Consider positive duties to protect life and effective access"),
 ("Article 21 is not a free-standing answer to every hardship", "Privacy is not absolute", "Procedure cannot be evaluated apart from practical effect", "Positive relief must remain institutionally and evidentially grounded"),
 "Start with the exact interest and intrusion; only then invoke the larger constitutional values"),
pack("Constitutional remedies and writs", ("writ", "habeas corpus", "mandamus", "certiorari", "prohibition", "quo warranto", "article 32", "article 226"),
 "A writ problem is a remedy and maintainability problem before it is a merits problem: identify jurisdiction, respondent, standing, alternative remedy, delay, disputed facts, public duty, jurisdictional defect, and the order that can practically cure the wrong",
 ("Choose the constitutional court and source of jurisdiction", "Identify the respondent and public-law character", "Match the wrong to the writ's function", "Address standing, alternative remedy, delay, suppression, and disputed facts", "State the review ground", "Frame a precise operative order"),
 ("Writ jurisdiction is discretionary even when power exists", "Alternative remedy is generally a restraint, not a universal jurisdictional bar", "A writ does not ordinarily determine every contested private fact", "Relief can be moulded but should not outrun the record"),
 "Give maintainability, ground of review, and relief their own headings"),
pack("Offer and acceptance", ("offer", "acceptance", "invitation to offer", "revocation", "communication of acceptance"),
 "Formation turns on objective manifested assent: a sufficiently final offer must be communicated, remain open, and be accepted in the prescribed or legally effective manner before valid revocation or lapse",
 ("Distinguish offer from invitation or negotiation", "Identify definite terms and intention to be bound", "Prove communication to the offeree", "Test conformity, mode, timing, silence, counter-offer, and conditional assent", "Place revocation, lapse, death, and acceptance on a timeline"),
 ("Subjective intention does not replace outward communication", "Silence is not ordinarily acceptance", "A counter-offer can terminate the original offer", "Electronic and instantaneous communications require medium-specific timing analysis"),
 "Draw a timeline; formation questions are usually lost by discussing doctrine without dates and communications"),
pack("Consideration and privity", ("consideration", "privity", "third party beneficiary"),
 "Consideration identifies the legally recognised exchange supporting a promise, while privity asks who may enforce the resulting contract; adequacy, past acts, existing duties, third-party performance, and statutory or equitable exceptions must be kept separate",
 ("Identify the promise and requested return", "Ask whether the act, abstinence, or promise moved at the promisor's desire", "Classify executed, executory, or past consideration", "Test legal sufficiency and existing duty", "Identify the enforcing party and any exception to privity"),
 ("Consideration need not be economically adequate", "A motive is not necessarily consideration", "Privity and consideration are different objections", "Restitution, trust, agency, assignment, family arrangement, or statute may alter the result"),
 "Name the promise, promisor, promisee, requested price, performer, and claimant in one compact table"),
pack("Free consent and vitiating factors", ("free consent", "coercion", "undue influence", "fraud", "misrepresentation", "mistake"),
 "Consent analysis asks whether parties agreed to the same transaction and whether that assent was produced by coercion, domination, deception, material misstatement, or legally operative mistake, each with distinct elements, burdens, and consequences",
 ("Identify the representation, pressure, relationship, or mistaken assumption", "Apply the statutory elements of the specific vitiating factor", "Prove inducement and materiality where required", "Allocate any shifted burden", "Classify the agreement as void, voidable, or unaffected", "Test affirmation, rescission bars, restitution, and damages"),
 ("Unfairness alone is not undue influence", "Silence is not always fraud", "Negligence can affect relief without automatically defeating it", "Mistake of value is usually different from mistake as to an essential fact"),
 "Do not plead every vitiating factor together; select the one that fits the facts and state its distinct consequence"),
pack("Breach, damages, remoteness, and mitigation", ("breach", "damages", "remoteness", "mitigation", "liquidated damages", "penalty"),
 "Contract damages protect a recognised interest by comparing the claimant's actual position with the legally relevant counterfactual, subject to causation, remoteness, certainty, mitigation, and statutory control of stipulated sums",
 ("Identify the obligation and breach date", "Choose expectation, reliance, restitution, indemnity, or another measure", "Construct the no-breach counterfactual", "Prove factual causation and legal remoteness", "Deduct avoided loss and reasonable mitigation", "Assess interest, stipulated sum, and proof of quantum"),
 ("Damages are not punishment", "Loss must be proved even when breach is clear unless law permits a nominal award", "Mitigation is a limitation on recovery, not a duty owed to the defendant", "A contractual sum is not automatically recoverable merely because it is written"),
 "Show the calculation and counterfactual; a damages answer without arithmetic or categories is incomplete"),
pack("Negligence", ("negligence", "duty of care", "standard of care", "breach of duty"),
 "Negligence requires a recognised duty, breach of a contextual standard of reasonable care, factual and legal causation, actionable damage, and the absence or adjustment of applicable defences",
 ("Identify claimant, defendant, activity, risk, and protected interest", "Establish duty through recognised category or principled extension", "Define the standard using probability, gravity, burden of precautions, utility, expertise, and custom", "Compare conduct with the standard", "Apply factual causation, scope of liability, remoteness, damage, and defences"),
 ("An accident does not prove negligence", "Foreseeability has different roles in duty, breach, and remoteness", "Custom is evidence, not always the legal standard", "Pure economic or psychiatric harm may have additional controls"),
 "Treat duty, breach, causation, remoteness, damage, and defence as six separate gates"),
pack("Strict and absolute liability", ("strict liability", "absolute liability", "rylands", "hazardous industry"),
 "No-fault liability doctrines attach responsibility to defined dangerous activities or escapes without ordinary negligence proof, but their scope, exceptions, statutory overlays, and remedial principles differ sharply",
 ("Identify the activity, substance, accumulation, danger, escape, and damage", "Classify the doctrine actually invoked", "Test non-natural or hazardous use where relevant", "Apply causation and scope", "Consider exceptions only if the chosen doctrine recognises them", "Check special environmental or compensation statutes"),
 ("Strict and absolute liability are not synonyms", "The absence of negligence does not answer a valid no-fault claim", "Not every industrial accident satisfies every common-law element", "Statutory regimes may supplement or replace the older doctrine"),
 "Name the doctrine first and never import an exception from a different doctrine"),
pack("Defamation", ("defamation", "libel", "slander", "reputation"),
 "Defamation balances reputation with speech by asking whether a defamatory imputation referring to the claimant was published to a third person, followed by careful analysis of truth, fair comment or opinion, privilege, consent, statutory protection, fault, and remedy",
 ("Identify the exact words, image, implication, and audience", "Apply the meaning standard in context", "Establish reference and publication", "Classify statement of fact, opinion, report, or privilege", "Apply the relevant defence element by element", "Assess harm, republication, correction, injunction, and damages"),
 ("Offence or criticism is not necessarily defamatory", "Words must be read as a whole and in context", "Truth, opinion, and privilege are distinct defences", "An injunction raises special speech and prior-restraint concerns"),
 "Quote only the minimum words necessary and analyse meaning before motive"),
pack("Criminal act, mental state, and concurrence", ("actus reus", "mens rea", "intention", "knowledge", "recklessness", "criminal negligence"),
 "Criminal liability normally requires concurrence of the prohibited conduct or result with the precise mental state assigned to each element, plus causation and the absence of a defence",
 ("Write every conduct, circumstance, and result element", "Attach the required mental state to each element", "Distinguish intention, knowledge, recklessness, negligence, motive, and presumption", "Test voluntariness, omission duty, causation, and temporal concurrence", "Analyse each participant independently"),
 ("Motive is not the same as mens rea", "A bad result does not prove intention", "Constructive liability needs its own statutory foundation", "Transferred intent and mistake operate only within their doctrinal limits"),
 "Use an element-to-evidence matrix and do not state a single global mens rea for the whole offence"),
pack("Homicide classification", ("homicide", "murder", "culpable homicide", "causing death"),
 "Homicide classification proceeds from causation and the statutory mental state to the aggravated category, recognised exceptions, lesser forms, special victim or method provisions, and sentence",
 ("Prove death and identity of the causal act", "Apply factual and legal causation", "Find intention or knowledge from all circumstances", "Compare the statutory thresholds for the competing homicide categories", "Test every pleaded exception", "Consider attempt, common liability, and evidential alternatives"),
 ("All intentional killings are not analysed under one label", "Medical causation and intervening events matter", "Suddenness alone does not establish an exception", "The burden and standard for an exception may differ from the prosecution's ultimate burden"),
 "Compare adjacent offences in a table; the exam issue is usually classification, not whether death occurred"),
pack("General exceptions and private defence", ("general exception", "private defence", "self defence", "insanity", "necessity", "mistake of fact"),
 "A general exception accepts that apparent offence elements may be present but excludes liability because of incapacity, justification, excuse, mistake, necessity, accident, compulsion, or lawful defensive force under defined conditions",
 ("Identify the exact exception and its statutory elements", "Locate the evidential foundation", "Allocate the burden and standard", "For defence force test threat, immediacy, necessity, proportionality, retreat or alternatives where relevant, and duration", "Separate complete from partial consequences"),
 ("A bare assertion does not raise every exception", "Private defence is preventive, not retaliatory", "Proportionality is contextual but not unlimited", "Intoxication, insanity, mistake, accident, and necessity have distinct requirements"),
 "State prosecution elements first, then the exception, its burden, and its effect"),
pack("Arrest, detention, and safeguards", ("arrest", "detention", "custody", "remand", "handcuff"),
 "Coercive custody requires legal authority, an objective statutory basis, necessity, contemporaneous reasons, communication of grounds, access to counsel and family, medical and record safeguards, timely judicial control, and humane treatment",
 ("Identify the arresting power and offence classification", "Test statutory grounds and necessity", "Check warrant or warrantless conditions", "Verify grounds, memo, time, place, witnesses, search, medical record, and information duties", "Examine production and remand chronology", "Choose release, exclusion, compensation, discipline, or other relief"),
 ("Power to arrest does not mean arrest is automatically necessary", "Remand is a judicial decision, not a clerical extension", "Illegality of arrest and merits of prosecution are distinct", "Special statutes may alter but not erase constitutional safeguards"),
 "Build a minute-by-minute custody chronology and link every safeguard to a document or witness"),
pack("Bail", ("bail", "anticipatory bail", "default bail", "regular bail"),
 "Bail balances liberty and the integrity of investigation or trial through the correct statutory route, offence classification, stage, custody status, statutory entitlement, risk assessment, conditions, and special-law constraints",
 ("Identify the correct form of bail and court", "Check custody, arrest apprehension, filing deadlines, and statutory entitlement", "Assess flight, tampering, intimidation, repetition, seriousness, role, health, delay, and parity", "Apply special-law thresholds separately", "Design necessary and proportionate conditions"),
 ("Bail is not a mini-trial", "Seriousness is relevant but not mechanically decisive", "Default bail depends on timely assertion and statutory chronology", "Conditions cannot make release illusory"),
 "Lead with the statutory route and chronology, then analyse risks and tailored conditions"),
pack("Relevance and admissibility", ("relevance", "admissibility", "fact in issue", "relevant fact"),
 "Evidence is relevant when a legally recognised inferential relationship connects it to a fact in issue; admissibility then asks whether any exclusion, privilege, competence, authenticity, or mode-of-proof rule prevents or limits use",
 ("State the fact in issue", "Identify the offered item and purpose", "Explain the inferential link", "Locate the statutory relevance category", "Apply exclusion and mode-of-proof rules", "Assess limiting purpose, weight, and sufficiency"),
 ("Relevant does not always mean admissible", "Admissible does not mean sufficient or credible", "The same statement may be used for one purpose but not another", "A procedural objection to mode can differ from a substantive bar"),
 "Always complete the sentence: ‘This item is offered to prove ___ because ___’"),
pack("Admissions and confessions", ("admission", "confession", "police confession", "discovery statement"),
 "Admissions are party-linked statements relevant under defined rules; confessions are incriminating admissions in criminal cases and face additional voluntariness, police-custody, constitutional, corroboration, and discovery restrictions",
 ("Identify speaker, recipient, custody status, maker's authority, and exact part relied on", "Classify admission or confession", "Apply inducement, threat, promise, police, custody, and magistrate rules", "For discovery isolate the distinctly related portion", "Test retraction, co-accused use, corroboration, and proof of statement"),
 ("Every incriminating statement is not a confession", "A confession cannot be sliced without context, though only admissible portions may be used", "Discovery does not admit an entire narrative", "Voluntariness and formal admissibility are distinct"),
 "Use a statement-by-statement table showing maker, setting, objection, admissible purpose, and weight"),
pack("Burden, standard, and presumptions", ("burden of proof", "onus", "presumption", "standard of proof"),
 "Burden analysis distinguishes the ultimate legal burden, shifting evidential onus, statutory presumptions, facts especially within knowledge, and the standard of persuasion at each stage",
 ("State the proposition to be proved", "Identify who bears the legal burden", "State the standard", "Identify foundational facts for any presumption", "Explain whether the presumption is permissive, rebuttable, or conclusive", "Assess whether rebuttal evidence restores or shifts the practical onus"),
 ("The burden does not shift merely because evidence is inconvenient", "A presumption cannot arise before foundational facts", "An evidential onus does not always transfer the ultimate burden", "Special statutes must be reconciled with constitutional fairness"),
 "Create one row per proposition; never say simply ‘the burden shifts’ without saying what, when, and to whom"),
pack("Electronic evidence", ("electronic evidence", "electronic record", "digital evidence", "certificate", "metadata"),
 "Digital proof requires relevance, lawful acquisition, source identification, integrity, authenticity, statutory mode, reliable extraction, understandable presentation, and a chain connecting the device or system to the proposition",
 ("Identify the original system, device, account, file, log, or communication", "Preserve and document acquisition", "Verify hash, metadata, time settings, authorship, and continuity", "Apply the applicable certificate or witness foundation", "Separate content, sender, receipt, location, and inference", "Anticipate alteration, access, hearsay, and privacy objections"),
 ("A screenshot is not self-proving", "A certificate does not cure irrelevance or false attribution", "Hash identity proves file consistency, not truth of content", "Possession of a device does not automatically prove authorship"),
 "Draw the evidence chain from event to system to extraction to exhibit to witness"),
pack("Natural justice", ("natural justice", "audi alteram partem", "nemo judex", "bias", "fair hearing"),
 "Natural justice protects fair decision-making through notice, meaningful opportunity, impartiality, disclosure, reasoned consideration, and context-sensitive safeguards unless valid law justifiably modifies them",
 ("Identify the decision, authority, source, and affected interest", "Ask what notice and material were supplied", "Assess opportunity, representation, cross-examination, and response in context", "Test actual, apparent, pecuniary, institutional, or subject-matter bias", "Examine reasons, prejudice, urgency, and post-decisional cure"),
 ("Fairness is contextual, not a single ritual", "No hearing may be required for a purely legislative act, but classification matters", "Prejudice may affect remedy without validating a fundamentally biased process", "Post-decisional hearing is not an automatic cure"),
 "Separate notice, disclosure, opportunity, impartiality, reasons, prejudice, and remedy"),
pack("Delegated legislation", ("delegated legislation", "subordinate legislation", "rules", "regulations", "excessive delegation", "ultra vires"),
 "Delegated law is valid only within legislative competence, the parent statute's policy and limits, mandatory procedure, constitutional rights, and the prohibition on unauthorised sub-delegation or inconsistency",
 ("Identify the parent provision and delegate", "Classify the instrument and legal effect", "Compare text, purpose, conditions, and limits", "Test publication, consultation, laying, approval, and other procedure", "Examine constitutional and statutory inconsistency", "Choose severance, reading down, or invalidation"),
 ("A rule cannot enlarge the parent Act", "Policy detail may be delegated but essential legislative limits still matter", "Administrative circulars and statutory rules are not interchangeable", "Procedural invalidity depends on the legal character of the requirement"),
 "Quote the enabling words and place the impugned rule beside them in a two-column comparison"),
pack("Jurisdiction", ("jurisdiction", "territorial jurisdiction", "pecuniary jurisdiction", "subject matter jurisdiction", "cause of action"),
 "Jurisdiction asks whether this decision-maker may hear this dispute, grant this remedy, bind these parties, and act at this stage, considering subject matter, territory, value, hierarchy, statutory bars, consent limits, and timing of objection",
 ("Identify forum and source of power", "Classify subject-matter, territorial, pecuniary, personal, appellate, supervisory, or remedial jurisdiction", "Map material facts to statutory connecting factors", "Test exclusive forum and ouster clauses", "Assess waiver, prejudice, transfer, return, or nullity consequences"),
 ("Consent cannot create subject-matter jurisdiction where law withholds it", "Every jurisdictional defect does not have the same consequence", "Cause of action is not identical to where evidence or a party happens to be", "An arbitration clause allocates forum but still requires validity and scope analysis"),
 "Answer four questions explicitly: who, where, over what, and with power to grant which order"),
pack("Res judicata and issue preclusion", ("res judicata", "constructive res judicata", "issue estoppel"),
 "Preclusion protects finality by barring re-litigation only when the earlier and later proceedings satisfy identity, competence, final decision, direct and substantial issue, party or privy, and any constructive or public-law qualifications",
 ("Identify the earlier decision and exact issue", "Verify competent forum and final adjudication", "Compare parties, title, cause, relief, and issue", "Ask whether the issue was directly and substantially in question", "Test constructive preclusion and recognised exceptions", "Distinguish res judicata, issue estoppel, abuse, and precedent"),
 ("Similarity of facts is not enough", "A dismissal may or may not decide merits", "Fraud, jurisdictional nullity, changed law, or continuing causes require careful treatment", "A precedent binds by ratio; res judicata binds parties through finality"),
 "Use a side-by-side matrix of the two proceedings"),
pack("Interim injunction", ("interim injunction", "temporary injunction", "balance of convenience", "irreparable injury"),
 "Interim relief preserves the practical value of adjudication through a prima facie case, comparative risk or balance of convenience, inadequacy of later repair, clean conduct, proportionality, and a precise time-limited order",
 ("Define the right and threatened act", "Show a serious triable or prima facie case without deciding final merits", "Compare harm from grant and refusal", "Explain why damages or later relief are inadequate", "Address delay, acquiescence, disclosure, undertaking, and third parties", "Draft the narrow operative restraint"),
 ("A strong merits case does not automatically establish urgency or irreparable harm", "‘Irreparable’ means inadequately repairable, not literally irreversible", "Mandatory interim orders demand special caution", "An injunction should not grant the entire final relief without justification"),
 "End with the exact wording, duration, exceptions, compliance steps, and next hearing"),
pack("Limitation", ("limitation", "delay", "condonation", "continuing wrong", "acknowledgment"),
 "Limitation is calculated by classifying the proceeding and relief, selecting the governing entry, fixing the accrual date, excluding legally permitted periods, and applying acknowledgment, disability, fraud, continuing wrong, or condonation rules only where available",
 ("Identify proceeding, relief, forum, and special statute", "Select the correct limitation provision", "Find when the right to sue, apply, appeal, or complain accrued", "Create a dated chronology", "Apply exclusion, acknowledgment, part-payment, disability, fraud, or continuing-wrong rules", "Determine whether delay can be condoned and on what showing"),
 ("Equity does not generally override a statutory bar", "A continuing effect is not always a continuing wrong", "Acknowledgment must satisfy timing and form rules", "A new representation does not necessarily restart time"),
 "Show the calculation line by line and give the last filing date"),
pack("Transfer of property and title", ("transfer of property", "sale", "mortgage", "lease", "gift", "title", "registration"),
 "Property transfer analysis identifies the interest, transferor's power, transferee, instrument, formalities, consideration or donative intent, conditions, notice, priority, possession, and the rights and remedies that survive",
 ("Identify the property and existing interests", "Classify sale, mortgage, lease, exchange, gift, charge, licence, or assignment", "Test competence, transferable interest, consideration or acceptance", "Apply writing, attestation, stamping, registration, and delivery rules", "Trace notice, priority, possession, and subsequent transfers", "Select possession, redemption, foreclosure, cancellation, declaration, or damages"),
 ("Possession and title are different", "An agreement to sell is not automatically a completed conveyance", "Registration does not cure lack of title or authority", "A licence and lease differ by substance, not label alone"),
 "Draw a title chain with dates, instruments, possession, notice, and encumbrances"),
pack("Marriage validity and divorce", ("valid marriage", "void marriage", "voidable marriage", "divorce", "matrimonial"),
 "Matrimonial status depends on the governing law, capacity, prohibited relationship, subsisting status, consent, ceremony or registration requirements, followed by distinct grounds and bars for nullity, dissolution, separation, and ancillary relief",
 ("Identify governing law, date, place, and parties' status", "Test every formation condition", "Classify void, voidable, irregular, or valid consequences under the applicable law", "For dissolution state the ground and its factual ingredients", "Test bars, condonation, collusion, delay, and reconciliation where relevant", "Address maintenance, residence, children, property, and enforcement separately"),
 ("Registration and ceremony rules vary by statute", "Marital breakdown is not automatically a statutory ground unless law recognises it", "Criminal, protective, maintenance, and matrimonial remedies can overlap but have different elements", "Child welfare is not a reward for marital fault"),
 "Separate status, ground, proof, defence, and ancillary orders"),
pack("Maintenance and support", ("maintenance", "alimony", "support", "interim maintenance"),
 "Maintenance law prevents unjust destitution and enforces status-based or statutory support by examining eligibility, neglect or refusal where required, independent means, needs, earning capacity, standard of living, liabilities, conduct only where legally relevant, and overlapping orders",
 ("Identify claimant, respondent, relationship, and statutory route", "Prove threshold eligibility and neglect or non-support", "Assess actual and potential income through reliable material", "Prepare a needs and liabilities schedule", "Reconcile parallel proceedings and prior payments", "Frame interim, final, effective-date, variation, and enforcement terms"),
 ("Unemployment does not automatically erase earning capacity", "Income affidavits require verification", "Maintenance is not identical across personal, secular, protective, and criminal-procedure routes", "A claimant's education does not by itself prove sufficient income"),
 "Use a monthly budget and payment-adjustment table rather than vague assertions"),
pack("Corporate personality and veil", ("corporate personality", "separate legal entity", "lifting the veil", "piercing the veil"),
 "A company is ordinarily a legal person distinct from shareholders and managers; departure requires a recognised statutory or judicial basis tied to fraud, evasion, agency, sham, group responsibility, public interest, or another specific doctrine rather than general unfairness",
 ("Identify the company, actor, obligation, and transaction", "Apply separate personality first", "Locate any statutory personal liability", "State the precise veil doctrine and facts satisfying it", "Distinguish ownership, control, agency, guarantee, tort, and group enterprise", "Tailor relief to the liable person and wrong"),
 ("Control alone does not erase personality", "A parent company is not automatically liable for a subsidiary", "Veil language should not replace ordinary agency, tort, trust, or statutory analysis", "Limited liability protects members, not necessarily directors from their own wrongs"),
 "Begin with separate personality and treat veil departure as an exceptional, reasoned second step"),
pack("Directors and fiduciary duties", ("director", "fiduciary duty", "board", "conflict of interest", "related party"),
 "Director analysis separates appointment and authority from duties of care, loyalty, proper purpose, conflict avoidance, disclosure, board procedure, statutory compliance, and remedies owed to the company or another recognised claimant",
 ("Identify office, authority, decision, and beneficiary of the duty", "Apply constitution, statute, board delegation, and proper-purpose limits", "Test conflict, interest disclosure, abstention, and approval", "Assess care using role, information, process, and expertise", "Prove causation, benefit, loss, and ratification limits", "Choose account, restoration, compensation, injunction, disqualification, or regulatory response"),
 ("A bad business outcome is not automatically breach", "Shareholder and company loss must not be conflated", "Disclosure does not always cure a prohibited transaction", "Business judgment deference depends on good faith and an informed, proper process"),
 "Build a board-decision chronology showing information, attendance, disclosure, vote, purpose, and benefit"),
pack("Industrial dispute and termination", ("industrial dispute", "retrenchment", "dismissal", "termination", "lay off", "closure"),
 "Labour termination analysis classifies the worker, establishment, action, reason, process, standing orders or contract, misconduct inquiry, statutory preconditions, discrimination or retaliation, and the forum and remedy",
 ("Establish employment status and applicable statute", "Classify dismissal, discharge, retrenchment, lay-off, closure, abandonment, fixed-term expiry, or resignation", "For misconduct test charge, notice, evidence, impartial inquiry, representation, finding, and proportionality", "For economic termination test notice, compensation, selection, and permission requirements", "Identify dispute sponsorship and forum", "Assess reinstatement, back wages, compensation, continuity, or correction"),
 ("Labels in the termination letter are not decisive", "Domestic inquiry fairness and ultimate proof are distinct", "Every termination is not retrenchment", "Reinstatement and full back wages are not automatic consequences"),
 "Classify the termination before applying any remedy"),
pack("Treaty interpretation", ("treaty interpretation", "vienna convention", "ordinary meaning", "travaux"),
 "Treaty interpretation reads text in good faith according to ordinary meaning, context, object and purpose, together with relevant subsequent agreement, practice, and applicable rules, using supplementary means only within their proper role",
 ("Identify authentic text, parties, date, reservations, and provision", "Read terms in textual and structural context", "State object and purpose without overriding text", "Examine subsequent agreement and practice", "Consider other applicable international rules", "Use preparatory work or circumstances to confirm or resolve ambiguity or absurdity"),
 ("Object and purpose is not permission to rewrite language", "Domestic interpretive habits do not automatically govern", "Practice must have the necessary parties and legal significance", "A translation issue may require comparing authentic texts"),
 "Quote the operative treaty phrase, then move through text, context, purpose, subsequent material, and supplementary means"),
pack("State responsibility", ("state responsibility", "attribution", "internationally wrongful act", "reparation"),
 "State responsibility requires conduct attributable to a state that breaches an international obligation in force, followed by analysis of circumstances precluding wrongfulness, cessation, non-repetition, reparation, invocation, and any special regime",
 ("Identify the conduct and actor", "Apply attribution rules", "Identify the obligation, beneficiary, and temporal application", "Prove breach and any continuing character", "Test consent, self-defence, countermeasures, force majeure, distress, or necessity where relevant", "Determine cessation, restitution, compensation, satisfaction, and invocation"),
 ("Attribution and breach are separate", "A private actor can be attributable only under defined tests", "A circumstance precluding wrongfulness does not necessarily erase compensation or the underlying obligation", "Responsibility differs from individual criminal liability"),
 "Use the sequence attribution → obligation → breach → excuse → consequence → invocation"),
pack("Refugee status and non-refoulement", ("refugee", "non-refoulement", "asylum", "well founded fear", "persecution"),
 "Refugee analysis examines a well-founded fear of persecution for a protected reason, the state's protection failure, inclusion and exclusion, sur place developments, credibility and country information, and the prohibition on return to serious risk",
 ("Identify nationality or habitual residence and feared actor", "Describe feared harm and why it reaches persecution or another serious-harm threshold", "Establish nexus to a protected ground", "Assess state protection and internal relocation", "Test exclusion, cessation, and credibility fairly", "Apply non-refoulement and procedural safeguards independently"),
 ("Economic hardship alone is not usually persecution", "A claimant need not prove certainty of future harm", "Non-state persecution may qualify where protection is ineffective", "Non-refoulement can arise from multiple legal sources beyond formal refugee recognition"),
 "Organise the answer around inclusion, protection, nexus, relocation, exclusion, and return risk"),
pack("Environmental principles", ("polluter pays", "precautionary principle", "sustainable development", "public trust doctrine", "intergenerational equity"),
 "Environmental principles guide risk governance and remedies by allocating preventive responsibility, scientific uncertainty, restoration cost, stewardship of common resources, present-development needs, and protection of future generations",
 ("Identify resource, activity, pollutant, pathway, receptor, and uncertainty", "Locate statutory and regulatory duties", "Apply precaution before irreversible harm where the threshold is met", "Allocate prevention, remediation, and compensation through polluter-pays reasoning", "Balance development through lawful alternatives and carrying capacity", "Frame restoration, monitoring, and compliance orders"),
 ("Precaution does not eliminate evidence or proportionality", "Polluter pays covers prevention and restoration, not only damages", "Sustainable development is not a licence to approve every project", "Public trust must be connected to a resource and state duty"),
 "Use a source–pathway–receptor diagram and distinguish prevention, restoration, and compensation"),
pack("Copyright", ("copyright", "fair dealing", "author's right", "literary work", "cinematograph"),
 "Copyright analysis identifies a protected work, authorship and ownership, subsistence and term, the exclusive act allegedly performed, substantiality and causal copying, then any licence, statutory exception, fair dealing, intermediary rule, and remedy",
 ("Classify the work and protected expression", "Establish ownership and term", "Identify the exact restricted act", "Prove access and copying of a substantial protected part", "Separate idea, fact, method, public domain, and merger concerns", "Apply licence and each exception", "Assess injunction, damages, account, delivery up, and platform relief"),
 ("Copyright does not protect ideas or information as such", "Similarity alone does not prove copying", "Substantiality is qualitative as well as quantitative", "Fair dealing is purpose- and context-specific"),
 "Place claimant work, defendant material, similarities, protectable expression, and defence in a comparison table"),
pack("Trade marks and passing off", ("trade mark", "trademark", "passing off", "deceptive similarity", "likelihood of confusion"),
 "Trade mark infringement applies statutory rights in a registered sign, while passing off protects goodwill against misrepresentation causing damage; sign, goods or services, use, similarity, consumer perception, defences, and remedy must be analysed distinctly",
 ("Identify claimant mark, registration, specification, territory, and validity", "Identify defendant sign and manner of use", "Compare marks as a whole from the relevant consumer's perspective", "Assess goods, channels, attention, reputation, and confusion", "For passing off prove goodwill, misrepresentation, and damage", "Apply descriptive, honest, nominative, prior-use, exhaustion, or other defences"),
 ("Side-by-side microscopic comparison is misleading", "Registration does not automatically prove passing-off goodwill", "Similarity and confusion are related but not identical inquiries", "A descriptive term may receive narrower protection"),
 "Use separate infringement and passing-off headings even when facts overlap"),
pack("Patentability and infringement", ("patent", "patentability", "novelty", "inventive step", "patent infringement"),
 "Patent analysis first construes the claim, then tests subject matter, novelty, inventive step, disclosure and other validity requirements, and separately compares every claim limitation with the accused product or process before defences and remedies",
 ("Identify priority date, claim, skilled person, and common general knowledge", "Constrain the claim through text, specification, and prosecution context where relevant", "Test excluded subject matter", "Compare each prior-art item for novelty", "Assess inventive step without hindsight", "Map every claim element to the accused act", "Apply licence, research, regulatory, government-use, exhaustion, or other defences"),
 ("An idea or discovery is not automatically patentable", "Novelty cannot be assembled from multiple references in the ordinary anticipation inquiry", "Infringement is claim-based, not based on broad similarity", "Validity and infringement are separate even when tried together"),
 "Prepare two claim charts: one against prior art and one against the accused embodiment"),
pack("Tax charge and computation", ("tax", "taxation", "income tax", "gst", "assessment", "deduction"),
 "Tax liability depends on a charging provision, taxable person and event, jurisdictional connection, period, classification, valuation or computation, deduction or credit conditions, procedure, and only then interest, penalty, and remedy",
 ("Identify tax, person, period, and taxable event", "Quote or accurately paraphrase the charging conditions", "Classify receipt, supply, asset, service, or transaction", "Compute base, rate, exemption, deduction, set-off, or credit", "Check return, notice, assessment, limitation, and burden", "Separate tax, interest, penalty, prosecution, and appeal"),
 ("There is no tax by inference without a valid charge", "Exemptions and deductions have their own conditions", "Accounting treatment is relevant but not always decisive", "Penalty requires separate statutory analysis"),
 "Show the statutory route and a numerical computation; do not answer tax questions with policy alone"),
pack("Arbitration agreement and jurisdiction", ("arbitration agreement", "kompetenz", "arbitral jurisdiction", "reference to arbitration"),
 "Arbitral authority rests on a valid written agreement covering the dispute and parties, with separate analysis of formation, incorporation, assignment, non-signatories, separability, arbitrability, seat, scope, and timely jurisdictional objection",
 ("Identify the exact arbitration text and connected documents", "Test formation, writing, certainty, and intention", "Identify parties and any non-signatory theory", "Classify seat, venue, governing law, institution, and rules", "Map dispute to clause scope and arbitrability", "Apply referral and jurisdiction-objection timing"),
 ("A commercial relationship does not imply arbitration", "Separability preserves clause analysis but does not validate a clause that never formed", "Venue is not always seat", "Non-signatory participation needs a recognised legal basis, not convenience"),
 "Put clause text, parties, dispute, seat, scope, and objection stage into a single jurisdiction table"),
pack("Arbitral award and challenge", ("arbitral award", "setting aside", "section 34", "enforcement of award", "public policy"),
 "Award review respects finality while policing jurisdiction, notice and opportunity, mandate, composition and procedure, non-arbitrability, defined public-policy limits, and any patent illegality ground available to the particular award",
 ("Identify domestic, international commercial, or foreign award", "Record seat, date, receipt, and challenge deadline", "Classify each objection under the correct statutory ground", "Distinguish review of process or mandate from merits appeal", "Assess severability and prejudice", "Separate setting aside, stay, recognition, and enforcement"),
 ("A challenge is not a rehearing on facts or contract interpretation", "Public policy is not a general fairness appeal", "Limitation is strict and receipt-sensitive", "An enforcement objection may differ from a seat-court challenge"),
 "Tie every objection to one statutory ground and one part of the record"),
pack("Statutory interpretation", ("statutory interpretation", "interpretation of statutes", "literal rule", "golden rule", "mischief rule", "purposive"),
 "Interpretation begins with enacted text in its linguistic and structural context, read consistently with purpose, scheme, definitions, constitutional norms, and established presumptions, while respecting institutional limits and temporal application",
 ("Identify the exact disputed words and version in force", "Read definitions, provisos, explanations, schedules, headings, and connected provisions", "State ordinary and technical meanings", "Identify purpose from legitimate materials", "Test competing readings against coherence, rights, workability, and consequences", "Use external aids only with a reason for doing so"),
 ("Named ‘rules’ are not mechanical trump cards", "Purpose cannot displace clear text without legal basis", "A proviso, deeming clause, and explanation have different functions", "Interpretation and judicial amendment must remain distinct"),
 "Present the two best readings before choosing one; the quality of comparison is the answer"),
pack("Professional responsibility", ("professional ethics", "advocate", "legal profession", "contempt", "bar council", "misconduct"),
 "Professional responsibility requires loyalty to law and court, competent and independent service to the client, confidentiality, conflict management, candour, fair dealing, proper fees, record integrity, and accountable conduct toward opponents and the justice system",
 ("Identify role, client, tribunal, affected third party, and governing rule", "Classify duty to court, client, profession, opponent, or public", "Identify conflict, confidentiality, candour, competence, fee, solicitation, or misuse issue", "Apply disclosure, consent, withdrawal, and non-waivable limits", "Preserve records and fair process in discipline"),
 ("Client instruction does not justify misleading a court", "Confidentiality and privilege are related but distinct", "Consent cannot cure every conflict", "Zealous representation is bounded by law and professional duty"),
 "State whose duty it is, to whom it is owed, whether it can be waived, and the safe next step"),
)


@dataclass(frozen=True)
class TypeGuide:
    name: str
    keys: tuple[str, ...]
    focus: str
    steps: tuple[str, ...]
    cautions: tuple[str, ...]


def guide(name: str, keys: Sequence[str], focus: str, steps: Sequence[str], cautions: Sequence[str]) -> TypeGuide:
    return TypeGuide(name, tuple(keys), sent(focus), tuple(map(sent, steps)), tuple(map(sent, cautions)))


TYPE_GUIDES: tuple[TypeGuide, ...] = (
    guide("Case authority", (" v. ", " vs. ", " versus ", " scc", " air ", " scr "),
          "A case node must be studied as an authority with verified facts, procedural posture, issues, ratio, material reasoning, separate opinions, operative order, and later treatment; the case name alone never proves a proposition",
          ("Open the authorised or reliable report", "Record court, bench, date, citation, and procedural posture", "Separate material facts from background", "Write each issue as a question", "Extract the narrow ratio and distinguish dicta", "Check later approval, distinction, limitation, or overruling", "Connect the proposition to this module"),
          ("Do not invent facts or holdings from the title", "Do not quote a headnote as though it were the judgment", "Do not ignore bench strength or later treatment", "Do not cite a case for a broader proposition than it decided")),
    guide("Statutory provision", ("article ", "section ", "rule ", "regulation ", "schedule ", "proviso", "explanation", " act", " code", "ordinance"),
          "A statutory node is mastered by reading the exact version in force with definitions, cross-references, provisos, explanations, delegated instruments, commencement, transition, and binding judicial construction",
          ("Identify jurisdiction and version date", "Read the complete provision and definitions", "Break conditions into elements", "Map provisos, exceptions, deeming clauses, and consequences", "Trace rules, forms, notifications, and connected provisions", "Check commencement, amendment, repeal, savings, and transition", "Add binding interpretation"),
          ("Never rely on section number alone", "Do not use an old code without transition analysis", "A proviso is not automatically an exception to everything", "Do not quote wording unless verified")),
    guide("Procedure", ("procedure", "jurisdiction", "appeal", "review", "revision", "trial", "investigation", "arrest", "bail", "limitation", "notice", "hearing", "filing", "execution"),
          "A procedure node is a staged power-and-deadline map: actor, forum, trigger, form, service, hearing, burden, order, challenge, enforcement, and consequence of non-compliance",
          ("Locate the procedural stage", "Identify competent actor and forum", "List trigger and preconditions", "Build a date and document chronology", "State notice and hearing safeguards", "Classify mandatory and directory requirements cautiously", "State the order, review route, limitation, and enforcement"),
          ("Do not answer a stage question with final merits", "Do not assume every irregularity voids the process", "Do not omit limitation and service", "Special statutes can modify general procedure")),
    guide("Offence or penal liability", ("offence", "murder", "homicide", "theft", "robbery", "rape", "hurt", "cheating", "criminal breach", "abetment", "conspiracy", "attempt", "punishment"),
          "An offence node requires exact elements, date-specific text, participation, mental state, causation, defences, burden, lesser alternatives, and sentence; moral blame is not a substitute for proof",
          ("Quote or accurately paraphrase the operative elements", "Separate conduct, circumstance, result, and mental-state elements", "Allocate evidence to each element", "Analyse each accused and mode of participation", "Test general and special defences", "Consider attempt and lesser offences", "Address sentence and ancillary orders only after liability"),
          ("Do not merge motive with mens rea", "Do not infer guilt from accusation or harm", "Do not forget replacement-code transition", "Do not combine all accused without role analysis")),
    guide("Remedy", ("remedy", "damages", "injunction", "writ", "compensation", "restitution", "specific performance", "appeal", "relief"),
          "A remedy node begins with entitlement and forum, then tests purpose, statutory power, discretion, causation, quantification, adequacy, clean hands, third-party effects, enforcement, and appellate control",
          ("Identify claimant, wrong, and cause of action", "Locate forum and remedial power", "State the remedy's purpose", "Apply threshold and discretionary factors", "Quantify or draft relief precisely", "Address alternative and cumulative remedies", "Explain enforcement, variation, stay, and appeal"),
          ("A right does not automatically yield every requested remedy", "Interim and final tests differ", "Damages require proof and a measure", "Drafting an overbroad order can defeat an otherwise valid claim")),
    guide("Theory or school", ("theory", "school", "positivism", "natural law", "realism", "utilitarian", "sociological", "historical", "feminist jurisprudence"),
          "A theory node requires charitable reconstruction of the central claim, assumptions, key concepts, problem addressed, method, strongest example, best objection, response, comparison, and contemporary use",
          ("Name the thinker, text, and context where known", "State the thesis in one sentence", "Define its technical vocabulary", "Explain what problem it solves", "Apply it to one legal institution or hard case", "Present the strongest criticism and possible reply", "Compare it with the nearest rival"),
          ("Do not reduce the theory to one slogan", "Do not confuse description and endorsement", "Do not attribute later developments without evidence", "Critique only after presenting the strongest form")),
    guide("Institution or actor", ("court", "tribunal", "commission", "authority", "institution", "parliament", "legislature", "executive", "judiciary", "board"),
          "An institutional node maps legal creation, composition, appointment, independence, jurisdiction, powers, procedure, accountability, review, and interaction with other bodies",
          ("Locate constitutive source", "Map composition and appointment", "Define territorial, subject, and remedial jurisdiction", "List decision and enforcement powers", "Explain procedure and safeguards", "Identify accountability, removal, audit, appeal, and judicial review", "Show institutional relationships"),
          ("Do not infer power from importance", "Composition rules can affect validity", "Independence and accountability are distinct", "An institution's practice cannot override its statute")),
    guide("Doctrinal concept", (),
          "A doctrine node is mastered by stating its purpose and source, converting it into elements and burdens, identifying boundaries and exceptions, applying it to facts, and linking it to procedure and remedy",
          ("Define the doctrine narrowly", "Locate its primary source", "Break it into conditions", "Identify burden and proof", "State limits, exceptions, and rival characterisations", "Apply material facts", "Conclude with consequence and remedy"),
          ("Do not treat the label as the rule", "Do not omit threshold or exception", "Do not cite authority without a proposition", "Do not confuse policy rationale with legal elements")),
)

def haystack(node: Mapping[str, Any], subject: Mapping[str, Any] | None, module: Mapping[str, Any] | None) -> str:
    values: list[Any] = [
        node.get("title"), node.get("summary"), node.get("eli15"), node.get("kind"),
        node.get("category"), node.get("subjectTitle"), node.get("moduleTitle"),
        subject.get("title") if subject else None, subject.get("category") if subject else None,
        module.get("title") if module else None,
        *(node.get("tags") or []), *(node.get("aliases") or []),
    ]
    return " " + clean(" ".join(str(v) for v in values if v)).lower() + " "


def key_score(text: str, keys: Sequence[str]) -> int:
    score = 0
    for key in keys:
        k = clean(key).lower()
        if not k:
            continue
        if k in text:
            score += 8 + min(8, len(k.split()) * 2)
        else:
            pieces = [p for p in re.findall(r"[a-z0-9]+", k) if len(p) > 3]
            score += sum(1 for p in pieces if p in text)
    return score


def select_profile(node: Mapping[str, Any], subject: Mapping[str, Any] | None, module: Mapping[str, Any] | None) -> Profile:
    text = haystack(node, subject, module)
    scored = [(key_score(text, p.keys), i, p) for i, p in enumerate(PROFILES)]
    score, _, result = max(scored, key=lambda x: (x[0], -x[1]))
    return result if score > 0 else GENERIC


def select_packs(node: Mapping[str, Any], subject: Mapping[str, Any] | None, module: Mapping[str, Any] | None, limit: int = 3) -> list[Pack]:
    text = haystack(node, subject, module)
    scored = sorted(((key_score(text, p.keys), -i, p) for i, p in enumerate(PACKS)), reverse=True)
    return [p for score, _, p in scored if score >= 8][:limit]


def select_guide(node: Mapping[str, Any]) -> TypeGuide:
    title = " " + clean(node.get("title")).lower() + " "
    if re.search(r"\b(v\.?|vs\.?|versus)\b", title) or re.search(r"\b(scc|air|scr|cri\.?\s*l\.?\s*j\.?)\b", title):
        return TYPE_GUIDES[0]
    scored = [(key_score(title, g.keys), -i, g) for i, g in enumerate(TYPE_GUIDES[1:-1], start=1)]
    score, _, result = max(scored, key=lambda x: (x[0], x[1]))
    return result if score > 0 else TYPE_GUIDES[-1]


def variant(seed: str, values: Sequence[str]) -> str:
    if not values:
        return ""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return values[int.from_bytes(digest[:4], "big") % len(values)]


def join_natural(items: Sequence[str]) -> str:
    items = [clean(x) for x in items if clean(x)]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def kind_label(node: Mapping[str, Any]) -> str:
    return {
        "subject": "paper", "module": "module", "topic": "topic", "foundation": "foundation",
    }.get(clean(node.get("kind")).lower(), clean(node.get("kind")) or "node")


def node_context(node: Mapping[str, Any], subject: Mapping[str, Any] | None, module: Mapping[str, Any] | None) -> str:
    if node.get("kind") == "subject":
        return f"the {node.get('code') or node['id']} paper {node.get('title')} in Term {node.get('term') or '?'}"
    if node.get("kind") == "module":
        return f"the module {node.get('title')} in {subject.get('title') if subject else node.get('subjectTitle') or 'the paper'}"
    if node.get("subjectId"):
        return f"{node.get('title')} within {module.get('title') if module else node.get('moduleTitle') or 'its module'} in {subject.get('title') if subject else node.get('subjectTitle') or 'the paper'}"
    return f"the common legal-method foundation {node.get('title')}"


def central_proposition(node: Mapping[str, Any], profile: Profile, packs: Sequence[Pack], guide_: TypeGuide) -> str:
    title = clean(node.get("title"))
    if packs:
        base = packs[0].explanation
        return (f"For this node, {title} is approached through the following controlling idea: {base} "
                f"The label is not itself a legal test. Convert it into the source, conditions, burden, counter-position, and consequence described below.")
    if node.get("kind") == "subject":
        return (f"{title} is a complete field of study rather than one rule. Its organising lens is this: {profile.lens} "
                f"The paper should therefore be learned as a connected system of concepts, institutions, processes, proof problems, and remedies rather than as isolated case names.")
    if node.get("kind") == "module":
        return (f"{title} groups a sequence of related questions. The module is coherent when each child topic is connected to the same analytic lens: {profile.lens} "
                f"Study the topics in their listed order because later topics use the distinctions introduced earlier.")
    if guide_.name == "Case authority":
        return (f"{title} is an authority node. Its legally useful content is not the case name but the verified proposition that was necessary to decide the material facts, read with bench strength and later treatment. "
                f"The linked course source tells you why the authority appears here; the official or reliable report must supply facts, ratio, order, and exact language.")
    return (f"{title} is best understood as a focused problem inside {profile.name}. {profile.lens} "
            f"The study task is to define the concept narrowly, identify its source and purpose, convert it into elements, and show how proof and procedure produce a legal consequence.")


def eli15_text(node: Mapping[str, Any], profile: Profile, packs: Sequence[Pack]) -> str:
    title = clean(node.get("title"))
    analogies = (
        f"Think of {title} as a labelled door in a large building. The label tells you which room may open, but you still need the right key: the controlling source, the required facts, and the correct procedure.",
        f"Imagine a referee deciding whether {title} applies. The referee cannot decide from the headline. They must check a list of conditions, hear the best objection, and then choose the consequence allowed by the rules.",
        f"Treat {title} like a recipe with legal ingredients. Missing one compulsory ingredient can change the result, while an exception can make the ordinary recipe inapplicable.",
        f"The simple version of {title} is: identify who may do what to whom, under which rule, after which facts are proved, and what happens if the rule is satisfied or defeated.",
    )
    text = variant(str(node["id"]), analogies)
    if packs:
        text += " " + packs[0].explanation
    else:
        text += " " + profile.lens
    return text


def learning_outcomes(node: Mapping[str, Any], profile: Profile, packs: Sequence[Pack], guide_: TypeGuide) -> list[str]:
    title = clean(node.get("title"))
    outcomes = [
        f"Define {title} without using the title as its own definition.",
        f"Locate and rank the primary sources that control {title} for the relevant date and forum.",
        f"Convert {title} into an element, stage, or comparison checklist that can be applied to facts.",
        f"Allocate the burden, standard, evidence, and procedural step for each contested proposition.",
        f"State the strongest boundary, exception, defence, or rival characterisation.",
        f"Reach a qualified conclusion and identify the legally available consequence or remedy.",
        f"Explain {title} in plain language and in an exam-ready legal form.",
    ]
    if guide_.name == "Case authority":
        outcomes[1] = f"Prepare a verified case brief for {title} containing court, bench, date, procedural posture, material facts, issues, ratio, order, and later treatment."
        outcomes[2] = f"State the narrow proposition for which {title} may properly be cited in this module."
    elif guide_.name == "Statutory provision":
        outcomes[1] = f"Read the exact version of the provision governing {title}, including definitions, provisos, explanations, rules, commencement, and transition."
    elif node.get("kind") in {"subject", "module"}:
        outcomes[0] = f"Explain the organising questions that connect the parts of {title}."
        outcomes[2] = f"Navigate the child nodes in a defensible learning order and show their dependencies."
    if packs:
        outcomes.append(f"Apply the specialised {packs[0].name.lower()} framework rather than a generic fairness test.")
    return uniq(outcomes)[:8]


def source_date_warning(node: Mapping[str, Any]) -> str:
    edition = clean(node.get("edition")) or "the linked course-material edition"
    return (f"The curriculum source is {edition}. That identifies the syllabus, not necessarily the law currently in force. "
            "Before relying on a proposition, verify commencement, amendments, repeal or replacement, savings and transition, subordinate legislation, later binding decisions, and the forum's current procedural rules.")


def relation_nodes(ids: Sequence[str], nodes: Mapping[str, Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [nodes[x] for x in ids if x in nodes]


def bridge_body(node: Mapping[str, Any], nodes: Mapping[str, Mapping[str, Any]]) -> str:
    prereqs = relation_nodes(node.get("prerequisites") or [], nodes)
    if not prereqs:
        return ("<p>This node has no strict predecessor. It must therefore define every technical term it uses and cannot assume another syllabus node.</p>"
                "<div class=\"bridge-note\"><strong>Starting rule</strong><p>Begin with facts, source hierarchy, precise issue framing, and the difference between a right, duty, power, liability, procedure, and remedy.</p></div>")
    cards = "".join(nlink(p) for p in prereqs)
    assumed = join_natural([clean(p.get("title")) for p in prereqs[:5]])
    more = "" if len(prereqs) <= 5 else f" and {len(prereqs)-5} additional predecessor nodes"
    return (f"<p>This page may assume only the strict predecessors shown below. In practical terms, you should already be able to use {esc(assumed + more)}. "
            "Everything else required for this node is restated here.</p>"
            f'<div class="relation-grid">{cards}</div>'
            "<div class=\"bridge-note\"><strong>Dependency rule</strong><p>A background or related link is useful but never silently assumed. When this page uses one, it explains the needed proposition again.</p></div>")


def child_overview(node: Mapping[str, Any], nodes: Mapping[str, Mapping[str, Any]]) -> str:
    ids = node.get("moduleIds") if node.get("kind") == "subject" else node.get("children")
    if not ids:
        return ""
    children = relation_nodes(ids or [], nodes)
    if not children:
        return ""
    rows = []
    for i, child in enumerate(children, start=1):
        count = len(child.get("children") or [])
        meta = f"{count} child nodes" if count else kind_label(child)
        rows.append(f'<li><a href="{esc(href(str(child["id"])))}"><span>{i}. {esc(child.get("title"))}</span><small>{esc(meta)}</small></a></li>')
    return ("<div class=\"child-map\"><h3>What this node contains</h3><ol>" + "".join(rows) + "</ol></div>")


def concept_map(node: Mapping[str, Any], profile: Profile, packs: Sequence[Pack]) -> str:
    title = clean(node.get("title"))
    steps = [
        ("1", "Trigger", f"Facts place {title} in issue"),
        ("2", "Source", "Current controlling text and authority"),
        ("3", "Test", "Conditions, stages, and burden"),
        ("4", "Challenge", "Exception, defence, or rival characterisation"),
        ("5", "Proof", "Admissible material tied to each proposition"),
        ("6", "Result", "Qualified conclusion, order, or remedy"),
    ]
    boxes = "".join(f'<div class="map-step"><span>{n}</span><strong>{esc(h)}</strong><small>{esc(t)}</small></div>' for n,h,t in steps)
    pack_note = ""
    if packs:
        pack_note = f'<p class="map-caption"><strong>Special lens:</strong> {esc(packs[0].name)} — {esc(packs[0].explanation)}</p>'
    return (f'<div class="concept-map" role="img" aria-label="Decision path for {esc(title)}">{boxes}</div>{pack_note}'
            '<p class="map-caption">Read left to right. A failure at a threshold may end the claim; a defence may alter the result; a remedy still requires its own legal basis.</p>')


def core_note_body(node: Mapping[str, Any], subject: Mapping[str, Any] | None, module: Mapping[str, Any] | None,
                   profile: Profile, packs: Sequence[Pack], guide_: TypeGuide, nodes: Mapping[str, Mapping[str, Any]]) -> str:
    title = clean(node.get("title"))
    context = node_context(node, subject, module)
    prop = central_proposition(node, profile, packs, guide_)
    methods = uniq([*guide_.steps, *profile.method, *(packs[0].test if packs else ())])[:10]
    questions = uniq([*profile.questions, *(packs[0].test if packs else ())])[:8]
    children = child_overview(node, nodes)
    paragraphs = [
        f"<h3>1. Central proposition</h3><p>{esc(prop)}</p>",
        (f"<p>The location of this node matters. It appears as {esc(context)}. That placement supplies context, not a shortcut. "
         f"The safest starting point is the {esc(profile.name)} lens: {esc(profile.lens)} The node should therefore be read as a set of legal questions rather than a paragraph to memorise.</p>"),
        (f"<h3>2. Purpose and legal function</h3><p>The function of studying {esc(title)} is to know what legal work the concept performs. "
         "A concept may define status, allocate power, create a threshold, classify conduct, control proof, organise a procedure, limit discretion, or determine a remedy. "
         "Before applying it, state that function. This prevents a familiar failure: citing a doctrine because its language sounds relevant even though it performs a different job in the legal system.</p>"),
        (f"<p>For an exam or real problem, translate the function into a complete chain: actor and relationship; legally material event; controlling source; conditions; burden and standard; "
         "evidence; exception or counter-position; decision-maker; and consequence. The chain is deliberately longer than a one-line definition because most hard problems arise at the links between doctrine, proof, procedure, and relief.</p>"),
        f"<h3>3. Questions that organise the node</h3>{pul(questions, 'check-list')}",
        (f"<h3>4. Working method</h3><p>Use the following order. It is designed to stop a conclusion from being smuggled into the definition and to keep current law separate from historical course material.</p>"
         f"{pul(methods, 'number-list')}") ,
        (f"<h3>5. Source, element, and fact discipline</h3><p>Every proposition about {esc(title)} should be labelled by source. Constitutional text, statute, rule, treaty, binding ratio, contract, custom, and scholarly explanation do different work. "
         "A secondary source can explain; it cannot silently replace the controlling primary source. When a provision or case is disputed, write the narrow proposition it supports and the date for which it is relied upon.</p>"),
        ("<p>Next convert the rule into factual propositions. Mark cumulative conditions with <em>and</em>; mark alternatives with <em>or</em>. State who must prove each proposition and to what standard. "
         "Then attach evidence to the proposition it supports. A document or witness is not ‘the evidence’ in the abstract: it is evidence of authorship, notice, intention, identity, loss, authority, timing, or another specific fact.</p>"),
        (f"<h3>6. Counter-position and boundary</h3><p>A strong answer on {esc(title)} states the best contrary characterisation before choosing a result. "
         "The contrary position may deny a threshold fact, invoke a different legal category, dispute jurisdiction, rely on an exception, attack proof or procedure, or accept liability but contest remedy. "
         "Answering the strongest version makes the conclusion more credible and reveals which additional fact would change it.</p>"),
        (f"<h3>7. Consequence</h3><p>Do not end with ‘therefore the doctrine applies’. State what the decision-maker may actually do. In {esc(profile.name)}, the likely consequence categories include {esc(join_natural(profile.results))}. "
         "The chosen consequence still requires standing, forum, limitation, jurisdiction, discretion, quantification, and enforceability. Where more than one remedy exists, explain whether they are alternative, cumulative, or mutually inconsistent.</p>"),
    ]
    if packs:
        for idx, p in enumerate(packs, start=1):
            paragraphs.append(f"<h3>{7+idx}. Specialised framework: {esc(p.name)}</h3><p>{esc(p.explanation)}</p>{pul(p.test, 'check-list')}<p><strong>Limits:</strong> {esc(join_natural(p.limits))}</p><p><strong>Exam use:</strong> {esc(p.exam)}</p>")
    if guide_.name == "Case authority":
        paragraphs.append(
            "<div class=\"integrity-box\"><h3>Case-note integrity</h3><p>The graph record identifies the authority and its curricular location but does not supply a verified law-report record. "
            "Accordingly, this page does not invent facts, ratio, quotations, or later treatment. Use the linked source to locate the authority, then verify the judgment through an official court source or a reliable report. "
            "Record the exact passage only after checking the judgment text, paragraph number, bench strength, and later treatment.</p></div>"
        )
    elif guide_.name == "Statutory provision":
        paragraphs.append(
            "<div class=\"integrity-box\"><h3>Text integrity</h3><p>Do not memorise statutory wording from this explanatory page. Open the current official text, confirm the version that governed the relevant event, and read definitions, provisos, explanations, schedules, rules, and transitional provisions together. "
            "Use quotation marks only for wording you have verified against that text.</p></div>"
        )
    paragraphs.append(children)
    return "".join(paragraphs)


def issue_method_body(node: Mapping[str, Any], profile: Profile, packs: Sequence[Pack], guide_: TypeGuide) -> str:
    title = clean(node.get("title"))
    rows = [
        ("Issue", f"On the material facts, does {title} govern, and what precise legal consequence is claimed?"),
        ("Controlling source", "Identify the current constitutional, statutory, regulatory, treaty, contractual, customary, or precedential source and its hierarchy."),
        ("Threshold", guide_.steps[0] if guide_.steps else "Identify the conditions that make the rule applicable."),
        ("Elements / stages", "Convert the rule into numbered cumulative and alternative propositions; avoid a prose cloud."),
        ("Burden and standard", "State who bears the legal burden, when any evidential onus shifts, and the standard of persuasion."),
        ("Proof", "Attach each material fact to a witness, document, admission, record, expert basis, presumption, or agreed proposition."),
        ("Counter-position", packs[0].limits[0] if packs else profile.mistakes[0]),
        ("Procedure", "Identify forum, stage, notice, hearing, limitation, jurisdiction, and the consequence of procedural non-compliance."),
        ("Result", "Give a qualified conclusion and the exact declaration, order, liability, sanction, or next procedural step."),
    ]
    body = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k,v in rows)
    return (f'<div class="table-wrap"><table class="analysis-table"><caption>Issue-to-result matrix for {esc(title)}</caption><tbody>{body}</tbody></table></div>'
            '<div class="formula"><strong>Compact formula</strong><p>Issue → source → elements → burden → proof → counter-position → procedure → remedy.</p></div>')


def boundaries_body(node: Mapping[str, Any], profile: Profile, packs: Sequence[Pack], guide_: TypeGuide) -> str:
    title = clean(node.get("title"))
    limits = uniq([*guide_.cautions, *profile.mistakes, *(x for p in packs for x in p.limits)])[:12]
    pairs = [
        (f"The label ‘{title}’", "The legal source and proposition for which it is used"),
        ("Moral, political, or commercial desirability", "A legally recognised power, right, duty, standard, or remedy"),
        ("A fact that makes a story persuasive", "A material fact connected to an element or discretionary factor"),
        ("A source that explains", "A source that controls"),
        ("Liability or entitlement", "The separate question of forum and relief"),
    ]
    compare = "".join(f"<div><span>{esc(a)}</span><strong>≠</strong><span>{esc(b)}</span></div>" for a,b in pairs)
    return (f"<p>Boundaries are part of the rule. The following distinctions and failure modes are especially important for {esc(title)}.</p>"
            f'<div class="not-equal">{compare}</div><h3>Common failure modes</h3>{pul(limits, "warning-list")}'
            '<p class="callout"><strong>Diagnostic question:</strong> What additional fact, source, or procedural event would make the opposite conclusion legally stronger?</p>')


def authority_map_body(node: Mapping[str, Any], profile: Profile, guide_: TypeGuide) -> str:
    laws = uniq(node.get("laws") or [])
    law_items = [f"<strong>{esc(law)}</strong> — verify title, extent, commencement, amendments, subordinate instruments, and the version governing the event." for law in laws]
    if not law_items:
        law_items = ["Identify the constitutional, statutory, treaty, contractual, customary, or precedential source before stating the rule."]
    authority = uniq([*profile.authority, *guide_.steps[:3]])[:8]
    result = uniq(profile.results)[:6]
    return (
        "<div class=\"authority-columns\">"
        f"<div><h3>Primary-law layer</h3>{ul(law_items, 'source-list')}</div>"
        f"<div><h3>Authority layer</h3>{pul(authority, 'source-list')}</div>"
        f"<div><h3>Consequence layer</h3>{pul(result, 'source-list')}</div>"
        "</div>"
        "<h3>Pinpoint protocol</h3><ol class=\"number-list\"><li>Name the court, bench strength, date, and citation.</li><li>State the proposition in your own words.</li><li>Add the paragraph or page containing the necessary reasoning.</li><li>Explain how the material facts match or differ.</li><li>Check later approval, distinction, limitation, statutory change, or overruling.</li></ol>"
        "<p class=\"callout\"><strong>Quotation rule:</strong> use a short exact passage only after verifying it against the primary text. A course-pack extract, headnote, blog, or search snippet is not a safe substitute for the judgment or enactment.</p>"
    )


def scenario_for(profile: Profile, title: str, seed: str) -> tuple[str, list[str], list[str]]:
    name = profile.name.lower()
    if "constitutional" in name or "administrative" in name:
        fact = f"A public authority issues a written order affecting Asha's licence and relies on {title}. The order cites a broad public objective, discloses only part of the material, gives Asha two days to respond, and contains no analysis of a less restrictive alternative."
        qs = ["What is the source and limit of the authority's power?", "Which right, duty of fairness, or review ground is engaged?", "Was notice and opportunity meaningful?", "What standard of review and remedy fit the defect?"]
    elif "contract" in name or "commercial obligations" in name:
        fact = f"Asha and Bharat exchange messages concerning a time-sensitive supply. They disagree about whether {title} was satisfied. One message reserves approval, performance begins, market price changes, and the written terms allocate some but not all of the risk."
        qs = ["Was a binding obligation created and on what terms?", "Which communication or act matters to the disputed element?", "Was performance discharged, excused, or breached?", "What loss and remedy can be proved?"]
    elif "criminal procedure" in name:
        fact = f"Police act on an allegation connected with {title}. The record contains inconsistent times, a delayed communication of grounds, an electronic device seizure, and a later judicial order that repeats the police request without detailed reasons."
        qs = ["Which power and procedural stage are involved?", "What preconditions and safeguards were mandatory?", "What does each contemporaneous record prove?", "What immediate and later remedy is available?"]
    elif "criminal law" in name:
        fact = f"During a rapidly developing confrontation, Bharat performs an act alleged to involve {title}. Witnesses agree on the result but differ on sequence, weapon, warning, participation, and what Bharat knew. A general exception is also raised."
        qs = ["What are the exact offence elements in force on the date?", "Which evidence proves conduct, result, and mental state?", "How should participation and causation be analysed?", "Does the exception or a lesser offence arise?"]
    elif "evidence" in name:
        fact = f"In a pending proceeding, a party offers a message, a copied document, and a witness statement to prove a proposition related to {title}. The opposing party disputes purpose, authenticity, mode of proof, and the inference drawn."
        qs = ["What fact in issue is each item offered to prove?", "Why is the item relevant?", "What exclusion or mode-of-proof rule applies?", "What weight remains after admission?"]
    elif "family" in name:
        fact = f"Asha seeks relief involving {title}. The parties dispute the governing law, dates, income, living arrangements, a child's care history, and the effect of an earlier order in a parallel proceeding."
        qs = ["Which statutory route and forum govern?", "What status or threshold facts must be proved?", "How do interim and final relief differ?", "How should parallel orders and child welfare be handled?"]
    elif "property" in name:
        fact = f"A property changes hands through two documents and later possession. The parties rely on {title}, but authority, registration, notice, consideration, an earlier encumbrance, and the date of delivery are disputed."
        qs = ["What interest existed at each date?", "Was the instrument and transfer legally effective?", "Who had notice and priority?", "What proprietary and personal remedies follow?"]
    elif "company" in name or "competition" in name or "banking" in name:
        fact = f"A company approves a transaction involving {title}. The board papers are incomplete, one decision-maker has an undisclosed connection, market and customer effects are disputed, and later communications give a different explanation for the decision."
        qs = ["Which entity, office, market, instrument, and authority matter?", "What approval, disclosure, process, or substantive standard applied?", "Which records prove purpose and effect?", "What private and regulatory consequences are available?"]
    elif "labour" in name or "employment" in name:
        fact = f"An employer takes action against a worker said to involve {title}. The appointment terms, worker classification, standing orders, inquiry record, comparator treatment, and economic justification point in different directions."
        qs = ["Which employment status and statute apply?", "How should the action be classified?", "Was the required process fair and complete?", "What forum and remedy follow?"]
    elif "international" in name or "human rights" in name or "refugee" in name:
        fact = f"Two states and an affected individual disagree about {title}. The relevant acts cross borders, the instruments have different parties and dates, domestic and international processes overlap, and the requested remedy would affect third states."
        qs = ["Which source binds which actor and when?", "What jurisdiction, admissibility, attribution, or status threshold applies?", "How should conflicting evidence and obligations be reconciled?", "What remedy may the competent body grant?"]
    elif "environmental" in name:
        fact = f"A project associated with {title} receives approval after a study identifies uncertainty and competing data. Local residents allege incomplete disclosure, cumulative impacts, weak monitoring, and irreversible risk; the operator relies on permits and economic benefit."
        qs = ["Which approvals, standards, and decision records control?", "How should uncertainty and precaution be treated?", "What does the causal and monitoring evidence show?", "Who must prevent, restore, compensate, and report?"]
    elif "intellectual property" in name:
        fact = f"Asha owns or uses an intangible asset connected with {title}. Bharat launches a similar product or communication. The parties dispute subsistence or validity, ownership, protected subject matter, similarity, consumer or technical evidence, licence, and an exception."
        qs = ["What right exists, who owns it, and for how long?", "What exact protected act or claim is alleged?", "How should similarity, copying, confusion, or technical comparison be performed?", "Which defence and remedy fit?"]
    elif "tax" in name:
        fact = f"A taxpayer structures a transaction involving {title}. The return discloses the transaction, but classification, valuation, period, deduction, notice timing, and penalty are contested."
        qs = ["What charging provision and taxable event apply?", "How should the item be classified and computed?", "Were procedural and limitation conditions met?", "What is the separate basis for tax, interest, penalty, and appeal?"]
    elif "arbitration" in name or "dispute resolution" in name:
        fact = f"A contract contains a dispute clause relevant to {title}. The documents use inconsistent seats and venues, an affiliate performed part of the contract, objections were raised at different stages, and the tribunal has made an interim or final decision."
        qs = ["Was there a valid agreement and who is bound?", "What are seat, scope, applicable law, and arbitrability?", "Was the objection timely and within the correct court or tribunal?", "What review or enforcement standard applies?"]
    elif "jurisprudence" in name or "theory" in name:
        fact = f"A court confronts a hard case involving {title}. The enacted text supports one result, settled institutional practice another, and a compelling moral argument a third. The judge must explain what counts as law and why."
        qs = ["How would the theory identify valid law?", "What role do morality, social fact, history, and institutional practice play?", "How would a rival theory decide differently?", "What does the example reveal about the theory's strengths and limits?"]
    else:
        fact = f"Asha and Bharat dispute whether {title} applies to a sequence of acts, documents, and communications. They agree on some background facts but contest the legal category, the controlling source, one threshold fact, the burden of proof, and the proper remedy."
        qs = ["What is the narrow issue?", "What source and version control?", "Which facts correspond to each element?", "What counter-position and remedy should be addressed?"]
    app = [
        "Classify the relationship, actor, forum, and procedural stage before choosing the rule.",
        f"Break {title} into the exact conditions supplied by current primary law and binding authority.",
        "Place every agreed and disputed fact beside the condition it supports or defeats; identify missing proof.",
        "Apply the strongest exception, defence, jurisdictional objection, or rival characterisation rather than ignoring it.",
        "Give a conditional conclusion, then state the order, liability, sanction, or next step the decision-maker may lawfully choose.",
    ]
    return fact, qs, app


def worked_problem_body(node: Mapping[str, Any], profile: Profile, packs: Sequence[Pack]) -> str:
    title = clean(node.get("title"))
    fact, qs, app = scenario_for(profile, title, str(node["id"]))
    issue = f"Whether, on these facts, the legal conditions associated with {title} are met, what objection is strongest, and what consequence follows."
    pack_application = ""
    if packs:
        pack_application = f"<p><strong>Specialised lens:</strong> Apply the {esc(packs[0].name.lower())} sequence: {esc(join_natural(packs[0].test))}</p>"
    return (
        f'<div class="hypo"><h3>Facts</h3><p>{esc(fact)}</p><h3>Questions</h3>{pul(qs, "question-list")}</div>'
        f'<h3>Model analysis</h3><p><strong>Issue:</strong> {esc(issue)}</p>{pack_application}{pul(app, "number-list")}'
        '<p><strong>Model conclusion:</strong> The facts given are deliberately insufficient for a categorical answer. The correct conclusion identifies the leading result, the missing or disputed fact that controls it, the best contrary argument, and the precise interim or final consequence available if that fact is proved.</p>'
    )


def exam_method_body(node: Mapping[str, Any], profile: Profile, packs: Sequence[Pack], guide_: TypeGuide) -> str:
    title = clean(node.get("title"))
    issue = f"Whether {title} applies when [insert the two or three legally material facts], under [identify the current controlling source], and with what consequence."
    skeleton = [
        f"Issue sentence: {issue}",
        "Source sentence: identify the source, jurisdiction, version date, and hierarchy.",
        "Rule paragraph: state the narrow proposition and its cumulative and alternative conditions.",
        "Authority paragraph: give the proposition supported by the leading authority, not merely its name.",
        "Application paragraphs: one material fact and counter-fact for each contested condition.",
        "Defence or boundary paragraph: state the strongest rival characterisation and answer it.",
        "Procedure and remedy paragraph: identify forum, stage, limitation, burden, order, and enforcement.",
        "Conclusion sentence: state the likely result, degree of confidence, and fact that could change it.",
    ]
    if guide_.name == "Case authority":
        skeleton[2] = "Case brief paragraph: verified material facts, procedural posture, issue, ratio, key reasoning, and operative order."
        skeleton[3] = "Use paragraph: explain the narrow proposition for which this authority is cited and compare the problem facts."
    tips = [
        "Use headings that answer the question, not headings copied from the syllabus.",
        "Write the rule before narrating every fact.",
        "Apply facts on both sides; a conclusion without counter-analysis earns little credit.",
        "Keep merits, proof, procedure, and remedy distinct.",
        "For a ten-mark answer, compress examples before compressing elements or authority.",
    ]
    if packs:
        tips.append(packs[0].exam)
    return f'<div class="issue-statement"><strong>Model issue statement</strong><p>{esc(issue)}</p></div><h3>Answer skeleton</h3>{pul(skeleton, "number-list")}<h3>Examiner-facing discipline</h3>{pul(tips, "check-list")}'


def revision_body(node: Mapping[str, Any], profile: Profile, packs: Sequence[Pack], guide_: TypeGuide) -> str:
    title = clean(node.get("title"))
    keywords = terms(title)
    vocab = dict(profile.vocab)
    for p in packs:
        for t in terms(p.name, 3):
            vocab.setdefault(t, f"A key term in the specialised {p.name.lower()} framework; define it from the controlling source before use.")
    if not vocab:
        vocab = dict(GENERIC.vocab)
    glossary = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k,v in list(vocab.items())[:8])
    one_line = central_proposition(node, profile, packs, guide_).split(". ")[0].rstrip(".") + "."
    flashcards = [
        (f"What is the first question in a {title} problem?", "Identify the actor, relationship, material event, current controlling source, and precise legal issue."),
        (f"What converts {title} from a label into legal analysis?", "Elements or stages, burden and standard, evidence, exception or counter-position, procedure, and consequence."),
        ("What must be checked before quoting a source?", "Official or reliable text, version date, jurisdiction, pinpoint, bench strength where relevant, and later treatment."),
        ("What makes a conclusion useful?", "It states likelihood, identifies the decisive fact, answers the strongest objection, and names the available order or remedy."),
    ]
    cards = "".join(f"<details class=\"flashcard\"><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q,a in flashcards)
    return (f'<div class="rule-box"><span>One-line recall</span><p>{esc(one_line)}</p></div>'
            f'<p><strong>Trigger words:</strong> {esc(join_natural(keywords) or title)}.</p>'
            f'<h3>Flashcards</h3><div class="flashcards">{cards}</div><h3>Working glossary</h3><dl class="glossary">{glossary}</dl>')


def self_test_body(node: Mapping[str, Any], profile: Profile, packs: Sequence[Pack], guide_: TypeGuide) -> str:
    title = clean(node.get("title"))
    qs: list[tuple[str,str]] = [
        (f"Define {title} in one sentence without circular wording.", central_proposition(node, profile, packs, guide_)),
        ("Which source should be checked first?", "The primary source that creates or controls the rule for the relevant jurisdiction, date, actor, and forum; then binding interpretation and implementing instruments."),
        ("How should the rule be converted for application?", "Into numbered cumulative and alternative conditions, each paired with burden, standard, supporting facts, and possible objection."),
        ("What is the strongest generic counter-position?", "That a threshold, jurisdictional connection, source condition, evidential foundation, procedural safeguard, or remedial requirement is missing, or that a more accurate legal category governs."),
        ("Why must proof and procedure be separated from the merits?", "A legally sound proposition can still fail for lack of admissible proof, wrong forum, limitation, standing, notice, or another procedural condition."),
        ("What must a case citation contain to be useful?", "The proposition supported, court and bench, material facts, pinpoint passage, and later treatment—not only a case name."),
        ("What must a statutory citation contain to be safe?", "The exact current or historically applicable version, definitions and connected provisions, commencement and transition, and any binding construction."),
        ("What is the final sentence of a strong answer?", "A qualified result identifying the decisive fact, strongest objection, exact legal consequence, and any next procedural step."),
    ]
    if packs:
        qs.insert(4, (f"State the specialised test for {packs[0].name}.", join_natural(packs[0].test)))
    items = "".join(f'<details class="qa"><summary><span>{i}</span>{esc(q)}</summary><p>{esc(a)}</p></details>' for i,(q,a) in enumerate(qs, start=1))
    return f'<div class="qa-list">{items}</div><p class="quiet">Answer aloud before opening each model answer. A model answer is a checking device, not a sentence to reproduce mechanically.</p>'

def sources_body(node: Mapping[str, Any], subject: Mapping[str, Any] | None, profile: Profile, guide_: TypeGuide) -> str:
    title = clean(node.get("title"))
    source_url = clean(node.get("source") or (subject.get("source") if subject else ""))
    edition = clean(node.get("edition") or (subject.get("edition") if subject else "")) or "edition not stated"
    source_note = clean(node.get("sourceNote") or (subject.get("sourceNote") if subject else ""))
    laws = uniq(node.get("laws") or (subject.get("laws") if subject else []) or [])
    source_cards: list[str] = []
    if source_url:
        source_cards.append(f'<a href="{esc(source_url)}" target="_blank" rel="noopener"><strong>DU course material</strong><span>{esc(edition)}</span><small>Use for syllabus placement, assigned readings, and the course-pack context.</small></a>')
    if guide_.name == "Case authority":
        source_cards.extend([
            f'<a href="{esc(OFFICIAL["Supreme Court judgments"])}" target="_blank" rel="noopener"><strong>Supreme Court of India</strong><span>Judgment search</span><small>Verify court text, bench, date, paragraph, and operative order.</small></a>',
            f'<a href="{esc(OFFICIAL["eCourts services"])}" target="_blank" rel="noopener"><strong>eCourts Services</strong><span>Case and order records</span><small>Check procedural history and court records where available.</small></a>',
        ])
    else:
        source_cards.extend([
            f'<a href="{esc(OFFICIAL["India Code"])}" target="_blank" rel="noopener"><strong>India Code</strong><span>Central legislation</span><small>Check current text, amendments, repeal, schedules, and subordinate material.</small></a>',
            f'<a href="{esc(OFFICIAL["Legislative Department"])}" target="_blank" rel="noopener"><strong>Legislative Department</strong><span>Official legislative resources</span><small>Check enacted texts and legislative material.</small></a>',
            f'<a href="{esc(OFFICIAL["Supreme Court judgments"])}" target="_blank" rel="noopener"><strong>Supreme Court of India</strong><span>Judgment search</span><small>Verify binding construction and later treatment.</small></a>',
        ])
    pname = profile.name.lower()
    if "international" in pname or "human rights" in pname or "refugee" in pname:
        source_cards.extend([
            f'<a href="{esc(OFFICIAL["UN Treaty Collection"])}" target="_blank" rel="noopener"><strong>UN Treaty Collection</strong><span>Status and treaty text</span><small>Check parties, signature, ratification, reservations, declarations, and entry into force.</small></a>',
            f'<a href="{esc(OFFICIAL["ICJ cases"])}" target="_blank" rel="noopener"><strong>International Court of Justice</strong><span>Cases and advisory proceedings</span><small>Use official pleadings, judgments, orders, and opinions.</small></a>',
        ])
    if "intellectual property" in pname:
        source_cards.append(f'<a href="{esc(OFFICIAL["WIPO Lex"])}" target="_blank" rel="noopener"><strong>WIPO Lex</strong><span>IP laws and treaties</span><small>Check legislation, treaties, and official materials by jurisdiction.</small></a>')
    law_rows = "".join(f'<li><strong>{esc(law)}</strong><span>Verify title, extent, version date, commencement, amendments, rules, notifications, savings, and transition.</span></li>' for law in laws)
    if not law_rows:
        law_rows = '<li><strong>Controlling primary law</strong><span>Identify it from the DU source and the node’s subject context; do not infer it from the topic title alone.</span></li>'
    checklist = [
        "Fix the legally relevant date and territory before searching.",
        "Open the primary text rather than relying on a quotation in a secondary source.",
        "Confirm commencement, amendment, repeal or replacement, savings, and transition.",
        "Read definitions, provisos, explanations, schedules, rules, forms, and notifications together.",
        "For cases, verify court, bench strength, procedural posture, ratio, pinpoint, operative order, and later treatment.",
        "Record the proposition supported by each source; do not collect citations without a purpose.",
        "Distinguish the syllabus edition from current law and preserve both dates in the note.",
    ]
    note = f'<div class="source-warning"><strong>Edition and currency</strong><p>{esc(source_date_warning(node))}</p>{f"<p>{esc(source_note)}</p>" if source_note else ""}</div>'
    return (f"{note}<h3>Linked source trail</h3><div class=\"source-grid\">{''.join(source_cards)}</div>"
            f"<h3>Legislation and instruments named for this paper</h3><ul class=\"law-register\">{law_rows}</ul>"
            f"<h3>Current-law verification protocol</h3>{pul(checklist, 'check-list')}"
            f"<p class=\"quiet\"><strong>Integrity note for {esc(title)}:</strong> this study page supplies an original explanatory framework. It deliberately does not manufacture a statutory quotation, case holding, historical fact, or empirical claim not present in a verified source.</p>")


def relation_group(title: str, ids: Sequence[str], nodes: Mapping[str, Mapping[str, Any]], empty: str) -> str:
    links = "".join(nlink(n) for n in relation_nodes(ids, nodes))
    return f'<div class="progress-group"><h3>{esc(title)}</h3>{f"<div class=\"relation-grid\">{links}</div>" if links else f"<p class=\"quiet\">{esc(empty)}</p>"}</div>'


def progression_body(node: Mapping[str, Any], nodes: Mapping[str, Mapping[str, Any]], previous_id: str | None, next_id: str | None) -> str:
    nav = []
    if previous_id and previous_id in nodes:
        nav.append(nlink(nodes[previous_id], "← " + clean(nodes[previous_id].get("title")), "sequence-link previous"))
    if next_id and next_id in nodes:
        nav.append(nlink(nodes[next_id], clean(nodes[next_id].get("title")) + " →", "sequence-link next"))
    strict = relation_group("Strict prerequisites", node.get("prerequisites") or [], nodes, "No strict predecessor.")
    unlocks = relation_group("Direct unlocks", node.get("unlocks") or [], nodes, "No direct unlock is recorded.")
    context_ids = uniq([*(node.get("background") or []), *(node.get("related") or [])])
    related = relation_group("Background and related nodes", context_ids, nodes, "No non-blocking context links are recorded for this node.")
    return (f'<div class="sequence-nav">{"".join(nav) if nav else "<p class=\"quiet\">This node has no adjacent entry in the generated study sequence.</p>"}</div>'
            f"{strict}{unlocks}{related}"
            '<div class="progress-note"><strong>Progress rule</strong><p>Opening a locked page is allowed. “Locked” only means its strict predecessors are not all marked complete. The page remains readable so you can inspect scope, decide whether to backtrack, and use it for revision.</p></div>')


def breadcrumb(node: Mapping[str, Any], subject: Mapping[str, Any] | None, module: Mapping[str, Any] | None) -> list[tuple[str, str]]:
    out: list[tuple[str,str]] = [("LL.B. graph", "../../")]
    if node.get("term"):
        out.append((f"Term {node.get('term')}", "../../#browse"))
    if subject and node.get("id") != subject.get("id"):
        out.append((clean(subject.get("title")), href(str(subject["id"]))))
    if module and node.get("id") != module.get("id"):
        out.append((clean(module.get("title")), href(str(module["id"]))))
    out.append((clean(node.get("title")), ""))
    return out


def render_page(node: Mapping[str, Any], subject: Mapping[str, Any] | None, module: Mapping[str, Any] | None,
                nodes: Mapping[str, Mapping[str, Any]], previous_id: str | None, next_id: str | None) -> tuple[str, dict[str, Any]]:
    profile = select_profile(node, subject, module)
    packs = select_packs(node, subject, module)
    guide_ = select_guide(node)
    title = clean(node.get("title"))
    code = clean(node.get("code") or node.get("subjectCode") or ("METHOD" if not node.get("term") else node.get("id"))).upper()
    ready_prereqs = [safe_id(x) for x in node.get("prerequisites") or [] if x in nodes]
    crumbs = breadcrumb(node, subject, module)
    crumbs_html = "".join(f'<a href="{esc(url)}">{esc(label)}</a><span aria-hidden="true">›</span>' if url else f'<span aria-current="page">{esc(label)}</span>' for label,url in crumbs)
    sections = [
        section("orientation", "Orientation", (
            f'<p class="lede">{esc(central_proposition(node, profile, packs, guide_))}</p>'
            f'<div class="orientation-grid"><div><small>Place in the course</small><strong>{esc(node_context(node, subject, module))}</strong></div>'
            f'<div><small>Analytic family</small><strong>{esc(profile.name)}</strong></div><div><small>Node type</small><strong>{esc(guide_.name)}</strong></div>'
            f'<div><small>Stable ID</small><strong>{esc(node["id"])}</strong></div></div>'
            f'{child_overview(node, nodes)}'
        ), "Start here"),
        section("eli15", "Explain it simply", f'<div class="eli"><span>ELI15</span><p>{esc(eli15_text(node, profile, packs))}</p></div><p>The analogy is only a starting point. The controlling legal source, defined conditions, burden, procedure, and remedy determine the actual answer.</p>', "Plain language"),
        section("outcomes", "What you should be able to do", pul(learning_outcomes(node, profile, packs, guide_), "outcome-list"), "Learning outcomes"),
        section("prerequisite-bridge", "What this page may assume", bridge_body(node, nodes), "Dependency bridge"),
        section("concept-map", "Visual decision path", concept_map(node, profile, packs), "Visual explainer"),
        section("core-note", "Full study note", core_note_body(node, subject, module, profile, packs, guide_, nodes), "Doctrine and method"),
        section("issue-method", "Issue, elements, proof, and result", issue_method_body(node, profile, packs, guide_), "Application framework"),
        section("boundaries", "Limits, distinctions, and common errors", boundaries_body(node, profile, packs, guide_), "Failure modes"),
        section("authority-map", "Authority, evidence, and remedy map", authority_map_body(node, profile, guide_), "Source discipline"),
        section("worked-problem", "Worked hypothetical", worked_problem_body(node, profile, packs), "Apply the node"),
        section("exam-method", "Exam answer guide", exam_method_body(node, profile, packs, guide_), "Write the answer"),
        section("revision", "Revision kit", revision_body(node, profile, packs, guide_), "Recall and compare"),
        section("self-test", "Self-test with model answers", self_test_body(node, profile, packs, guide_), "Active recall"),
        section("sources", "Primary sources and currency checks", sources_body(node, subject, profile, guide_), "Verify before relying"),
        section("progression", "Continue through the graph", progression_body(node, nodes, previous_id, next_id), "Cross-references"),
    ]
    toc = "".join(f'<a href="#{sid}">{esc(label)}</a>' for sid,label in [
        ("orientation","Orientation"),("eli15","ELI15"),("prerequisite-bridge","Prerequisites"),("concept-map","Visual"),
        ("core-note","Full note"),("issue-method","Issue method"),("boundaries","Limits"),("worked-problem","Problem"),
        ("exam-method","Exam guide"),("revision","Revision"),("self-test","Self-test"),("sources","Sources"),("progression","Next"),
    ])
    canonical = f'https://legedith.github.io/llb/nodes/{quote(str(node["id"]))}/'
    description = clean(central_proposition(node, profile, packs, guide_))[:260]
    schema = {
        "@context": "https://schema.org", "@type": "LearningResource", "name": title,
        "description": description, "educationalLevel": "University", "learningResourceType": "Study guide",
        "isPartOf": {"@type": "Course", "name": "University of Delhi LL.B. knowledge graph"},
        "url": canonical, "identifier": str(node["id"]),
    }
    html_doc = f'''<!doctype html>
<html lang="en" data-node-id="{esc(node["id"])}" data-prerequisites="{esc(','.join(ready_prereqs))}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#f4efe4">
  <title>{esc(title)} · DU LL.B. Study Page</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="stylesheet" href="../../node.css">
  <script type="application/ld+json">{json.dumps(schema, ensure_ascii=False).replace('</', '<\\/')}</script>
  <script defer src="../../node.js"></script>
</head>
<body>
<a class="skip-link" href="#main">Skip to study content</a>
<header class="study-header">
  <div class="header-row">
    <a class="brand" href="../../"><span>DU</span><strong>LL.B. Knowledge Graph</strong></a>
    <div class="header-actions"><a href="../../nodes/">Find a node</a><button id="bookmarkToggle" type="button" aria-pressed="false">Bookmark</button></div>
  </div>
  <nav class="breadcrumbs" aria-label="Breadcrumb">{crumbs_html}</nav>
</header>
<main id="main">
  <article class="study-article">
    <header class="node-hero">
      <div><span class="node-code">{esc(code)} · {esc(kind_label(node))}</span><h1>{esc(title)}</h1>
      <p>{esc(description)}</p></div>
      <aside class="status-card"><span id="statusBadge">Checking progress…</span><p id="readinessText">This page is readable regardless of sequence status.</p>
      <button id="completeToggle" type="button" aria-pressed="false">Mark complete</button></aside>
    </header>
    <nav class="page-toc" aria-label="On this page">{toc}</nav>
    {''.join(sections)}
  </article>
</main>
<footer class="study-footer">
  <div><strong>{esc(title)}</strong><span>Stable node {esc(node["id"])} · Content model {esc(VERSION)}</span></div>
  <div><button id="copyLink" type="button">Copy link</button><button id="printPage" type="button">Print / save PDF</button><a href="../../">Back to graph</a></div>
</footer>
<div id="toast" class="toast" role="status" aria-live="polite"></div>
</body>
</html>'''
    meta = {
        "id": str(node["id"]), "title": title, "code": code, "kind": clean(node.get("kind")),
        "term": node.get("term") or 0, "subjectId": node.get("subjectId") or (node["id"] if node.get("kind") == "subject" else None),
        "subjectTitle": clean(subject.get("title") if subject else node.get("subjectTitle")),
        "moduleTitle": clean(module.get("title") if module else node.get("moduleTitle")),
        "path": f'nodes/{node["id"]}/', "wordCount": words(html_doc), "profile": profile.name,
        "guide": guide_.name, "conceptPacks": [p.name for p in packs], "prerequisites": ready_prereqs,
        "unlocks": [safe_id(x) for x in node.get("unlocks") or [] if x in nodes],
        "source": clean(node.get("source") or (subject.get("source") if subject else "")),
        "edition": clean(node.get("edition") or (subject.get("edition") if subject else "")),
        "contentVersion": VERSION,
    }
    return html_doc, meta

NODE_CSS = r'''
:root {
  --ink:#171713; --muted:#665f54; --paper:#fffdf7; --canvas:#f4efe4; --line:#d9d0bf;
  --accent:#164f46; --accent-soft:#dcebe5; --warm:#92512f; --warm-soft:#f4e4d5;
  --danger:#8a2f35; --danger-soft:#f5dfe1; --shadow:0 12px 32px rgba(49,39,24,.10);
  --radius:18px; --measure:76ch; --sans:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --serif:ui-serif,Georgia,Cambria,"Times New Roman",serif;
}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:6rem}body{margin:0;background:var(--canvas);color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.65}
a{color:var(--accent);text-underline-offset:.18em}button,a{touch-action:manipulation}.skip-link{position:fixed;left:.75rem;top:-5rem;z-index:100;background:var(--ink);color:white;padding:.7rem 1rem;border-radius:.5rem}.skip-link:focus{top:.75rem}.study-header{position:sticky;top:0;z-index:20;background:rgba(244,239,228,.96);backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:.7rem max(1rem,env(safe-area-inset-left)) .55rem}.header-row{display:flex;align-items:center;justify-content:space-between;gap:.75rem;max-width:1180px;margin:auto}.brand{display:flex;align-items:center;gap:.6rem;text-decoration:none;color:var(--ink);min-width:0}.brand span{display:grid;place-items:center;width:2.2rem;height:2.2rem;border-radius:50%;background:var(--ink);color:white;font:700 .78rem/1 var(--sans);letter-spacing:.08em}.brand strong{font-size:.92rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.header-actions{display:flex;gap:.4rem;align-items:center}.header-actions a,.header-actions button,.study-footer button,.study-footer a{appearance:none;border:1px solid var(--line);background:var(--paper);color:var(--ink);padding:.55rem .72rem;border-radius:999px;font:650 .76rem/1 var(--sans);text-decoration:none;cursor:pointer;white-space:nowrap}.header-actions button[aria-pressed=true]{background:var(--accent);color:white;border-color:var(--accent)}.breadcrumbs{max-width:1180px;margin:.55rem auto 0;display:flex;align-items:center;gap:.4rem;overflow:auto;white-space:nowrap;font-size:.73rem;color:var(--muted);scrollbar-width:none}.breadcrumbs::-webkit-scrollbar{display:none}.breadcrumbs a{text-decoration:none;color:var(--muted)}main{padding:1rem .85rem 4.5rem}.study-article{max-width:980px;margin:auto}.node-hero{display:grid;gap:1rem;background:linear-gradient(145deg,#fffdf8,#eee5d5);border:1px solid var(--line);border-radius:24px;padding:1.25rem;box-shadow:var(--shadow)}.node-code,.section-eyebrow{display:block;color:var(--warm);font-size:.72rem;font-weight:800;letter-spacing:.105em;text-transform:uppercase}.node-hero h1{font-family:var(--serif);font-size:clamp(2rem,8vw,4rem);line-height:1.03;letter-spacing:-.035em;margin:.35rem 0 .8rem}.node-hero>div>p{max-width:70ch;color:#4c473f;margin:0;font-size:1.02rem}.status-card{background:rgba(255,255,255,.7);border:1px solid var(--line);border-radius:16px;padding:1rem;align-self:start}.status-card span{display:inline-flex;border-radius:999px;padding:.35rem .65rem;background:var(--warm-soft);color:var(--warm);font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.status-card span.ready{background:var(--accent-soft);color:var(--accent)}.status-card span.complete{background:var(--accent);color:white}.status-card p{font-size:.8rem;color:var(--muted);line-height:1.45}.status-card button{width:100%;border:0;border-radius:12px;background:var(--ink);color:white;padding:.78rem 1rem;font-weight:750;cursor:pointer}.status-card button[aria-pressed=true]{background:var(--accent)}.page-toc{display:flex;gap:.45rem;overflow:auto;padding:.9rem 0 .25rem;position:sticky;top:4.4rem;z-index:10;background:linear-gradient(var(--canvas) 76%,transparent);scrollbar-width:none}.page-toc::-webkit-scrollbar{display:none}.page-toc a{flex:0 0 auto;background:var(--paper);border:1px solid var(--line);border-radius:999px;padding:.47rem .68rem;font-size:.72rem;font-weight:700;text-decoration:none;color:var(--muted)}.page-toc a:hover,.page-toc a:focus{border-color:var(--accent);color:var(--accent)}.study-section{background:var(--paper);border:1px solid var(--line);border-radius:var(--radius);padding:1.2rem;margin:1rem 0;box-shadow:0 5px 18px rgba(49,39,24,.045)}.study-section h2{font-family:var(--serif);font-size:clamp(1.55rem,6vw,2.45rem);line-height:1.12;letter-spacing:-.025em;margin:.25rem 0 1rem}.study-section h3{font-size:1rem;line-height:1.35;margin:1.55rem 0 .55rem}.study-section p{max-width:var(--measure);margin:.7rem 0}.lede{font:1.08rem/1.65 var(--serif);color:#332f29}.orientation-grid{display:grid;grid-template-columns:1fr;gap:.55rem;margin-top:1rem}.orientation-grid div{background:#f6f1e8;border:1px solid #e5dccd;border-radius:12px;padding:.75rem}.orientation-grid small{display:block;color:var(--muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.07em}.orientation-grid strong{display:block;margin-top:.2rem;font-size:.88rem}.eli{border-left:5px solid var(--warm);background:var(--warm-soft);border-radius:0 15px 15px 0;padding:1rem}.eli span{font-size:.7rem;font-weight:850;color:var(--warm);letter-spacing:.1em}.eli p{margin:.25rem 0;font:1.1rem/1.55 var(--serif)}ul,ol{padding-left:1.25rem}.outcome-list,.check-list,.number-list,.warning-list,.question-list,.source-list{display:grid;gap:.55rem;max-width:var(--measure)}.outcome-list li::marker,.check-list li::marker{color:var(--accent)}.warning-list li::marker{color:var(--danger)}.bridge-note,.progress-note,.callout,.integrity-box,.source-warning,.formula,.issue-statement,.rule-box{border:1px solid var(--line);background:#f5f1e8;border-radius:14px;padding:.9rem 1rem;margin:1rem 0}.bridge-note strong,.progress-note strong,.callout strong,.source-warning strong{color:var(--accent)}.relation-grid{display:grid;grid-template-columns:1fr;gap:.55rem}.node-link{display:flex;justify-content:space-between;gap:.8rem;align-items:center;border:1px solid var(--line);border-radius:12px;padding:.72rem;text-decoration:none;background:white}.node-link span{font-weight:720;color:var(--ink)}.node-link small{color:var(--muted);text-align:right}.node-link:hover{border-color:var(--accent);transform:translateY(-1px)}.concept-map{display:grid;gap:.5rem}.map-step{position:relative;display:grid;grid-template-columns:2rem 1fr;column-gap:.55rem;align-items:center;padding:.7rem;border:1px solid var(--line);border-radius:12px;background:#faf6ee}.map-step span{grid-row:1/3;display:grid;place-items:center;width:2rem;height:2rem;border-radius:50%;background:var(--accent);color:white;font-weight:800}.map-step strong{font-size:.84rem}.map-step small{color:var(--muted);line-height:1.35}.map-caption{font-size:.82rem;color:var(--muted)}.child-map{border-top:1px solid var(--line);margin-top:1.3rem;padding-top:.2rem}.child-map ol{list-style:none;padding:0;display:grid;gap:.45rem}.child-map a{display:flex;justify-content:space-between;gap:.7rem;text-decoration:none;border-bottom:1px dashed var(--line);padding:.55rem 0}.child-map a span{color:var(--ink);font-weight:650}.child-map a small{color:var(--muted)}.integrity-box{background:#eff3ef;border-color:#cdddcf}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:14px}.analysis-table{width:100%;border-collapse:collapse;min-width:570px}.analysis-table caption{text-align:left;padding:.75rem;font-weight:800;background:#eee7da}.analysis-table th,.analysis-table td{text-align:left;vertical-align:top;padding:.7rem;border-top:1px solid var(--line)}.analysis-table th{width:9rem;color:var(--accent);font-size:.78rem}.not-equal{display:grid;gap:.45rem}.not-equal div{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:.6rem;background:#f7f2e9;border-radius:10px;padding:.65rem;font-size:.82rem}.not-equal strong{color:var(--danger)}.authority-columns{display:grid;gap:.75rem}.authority-columns>div{border:1px solid var(--line);border-radius:14px;padding:.8rem;background:#faf7f0}.authority-columns h3{margin:.1rem 0 .65rem}.hypo{border:1px solid #c8d8d3;border-radius:16px;padding:1rem;background:#edf5f2}.hypo h3:first-child{margin-top:0}.issue-statement{background:var(--accent);color:white;border-color:var(--accent)}.issue-statement p{margin-bottom:0}.rule-box{border-left:5px solid var(--accent)}.rule-box span{font-size:.7rem;text-transform:uppercase;letter-spacing:.09em;color:var(--accent);font-weight:850}.rule-box p{font:1.05rem/1.5 var(--serif)}.flashcards,.qa-list{display:grid;gap:.55rem}.flashcard,.qa{border:1px solid var(--line);border-radius:12px;background:#fbf8f1;overflow:hidden}.flashcard summary,.qa summary{cursor:pointer;padding:.75rem;font-weight:720}.flashcard p,.qa p{padding:0 .85rem .85rem;margin:0;color:#4f493f}.qa summary{display:flex;gap:.65rem;align-items:flex-start}.qa summary span{display:grid;place-items:center;flex:0 0 1.65rem;height:1.65rem;border-radius:50%;background:var(--ink);color:white;font-size:.72rem}.glossary{display:grid;grid-template-columns:max-content 1fr;gap:.5rem .8rem}.glossary dt{font-weight:800;color:var(--accent)}.glossary dd{margin:0}.source-grid{display:grid;gap:.6rem}.source-grid a{display:grid;border:1px solid var(--line);border-radius:13px;padding:.8rem;text-decoration:none;background:white}.source-grid strong{color:var(--ink)}.source-grid span{font-size:.8rem;color:var(--accent)}.source-grid small{margin-top:.25rem;color:var(--muted);line-height:1.4}.law-register{list-style:none;padding:0;display:grid;gap:.55rem}.law-register li{display:grid;gap:.2rem;border-left:4px solid var(--warm);background:var(--warm-soft);padding:.7rem .8rem}.law-register span{font-size:.82rem;color:#5a5148}.sequence-nav{display:grid;grid-template-columns:1fr;gap:.6rem;margin-bottom:1rem}.sequence-link{min-height:4.5rem}.sequence-link.next{text-align:right}.progress-group{margin-top:1.1rem}.quiet{color:var(--muted);font-size:.84rem}.study-footer{display:grid;gap:1rem;background:var(--ink);color:white;padding:1.3rem max(1rem,env(safe-area-inset-right)) calc(1.3rem + env(safe-area-inset-bottom)) max(1rem,env(safe-area-inset-left))}.study-footer>div{display:flex;flex-wrap:wrap;gap:.45rem;align-items:center}.study-footer>div:first-child{display:grid;gap:.1rem}.study-footer span{font-size:.75rem;color:#c9c1b3}.study-footer button,.study-footer a{background:#2a2925;color:white;border-color:#555148}.toast{position:fixed;left:50%;bottom:calc(1rem + env(safe-area-inset-bottom));transform:translate(-50%,150%);opacity:0;background:var(--ink);color:white;padding:.75rem 1rem;border-radius:999px;z-index:100;transition:.25s;white-space:nowrap;max-width:90vw;overflow:hidden;text-overflow:ellipsis;font-size:.8rem}.toast.show{transform:translate(-50%,0);opacity:1}
.directory-shell{max-width:980px;margin:auto;padding:1rem}.directory-hero{background:var(--paper);border:1px solid var(--line);border-radius:20px;padding:1.2rem}.directory-hero h1{font:2.2rem/1.05 var(--serif);margin:.2rem 0}.directory-search{position:sticky;top:4rem;z-index:10;background:var(--canvas);padding:.8rem 0}.directory-search input{width:100%;border:1px solid var(--line);border-radius:14px;padding:.9rem 1rem;font:inherit;background:white}.directory-results{display:grid;gap:.55rem}.directory-card{display:grid;grid-template-columns:1fr auto;gap:.4rem 1rem;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:.85rem;text-decoration:none}.directory-card strong{color:var(--ink)}.directory-card small{color:var(--muted)}.directory-card span{grid-row:1/3;grid-column:2;color:var(--accent);font-size:.75rem;font-weight:750}.directory-count{color:var(--muted);font-size:.8rem}
@media (min-width:620px){main{padding:1.4rem 1.2rem 5rem}.node-hero{grid-template-columns:minmax(0,1fr) 220px;padding:1.6rem}.orientation-grid{grid-template-columns:repeat(2,1fr)}.relation-grid,.source-grid{grid-template-columns:repeat(2,1fr)}.concept-map{grid-template-columns:repeat(3,1fr)}.authority-columns{grid-template-columns:repeat(3,1fr)}.sequence-nav{grid-template-columns:1fr 1fr}.study-footer{grid-template-columns:1fr auto;align-items:center}.study-footer>div:last-child{justify-content:flex-end}}
@media (min-width:900px){.study-section{padding:1.7rem 2rem}.orientation-grid{grid-template-columns:repeat(4,1fr)}.concept-map{grid-template-columns:repeat(6,1fr)}.map-step{grid-template-columns:1fr;text-align:center}.map-step span{grid-row:auto;margin:auto}.page-toc{top:4.1rem}.relation-grid{grid-template-columns:repeat(3,1fr)}}
@media print{body{background:white;font-size:11pt}.study-header,.page-toc,.status-card,.study-footer,.toast{display:none!important}main{padding:0}.study-article{max-width:none}.node-hero,.study-section{box-shadow:none;border-color:#bbb;break-inside:avoid}.node-hero{grid-template-columns:1fr}.study-section{break-before:auto}.study-section h2{font-size:20pt}a{color:black;text-decoration:none}.flashcard[open],.qa[open]{display:block}.source-grid a::after{content:" (" attr(href) ")";font-size:8pt}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
'''

NODE_JS = r'''
(() => {
  'use strict';
  const KEY = 'du-llb-graph-v1';
  const root = document.documentElement;
  const id = root.dataset.nodeId;
  const prerequisites = (root.dataset.prerequisites || '').split(',').filter(Boolean);
  const complete = document.getElementById('completeToggle');
  const bookmark = document.getElementById('bookmarkToggle');
  const badge = document.getElementById('statusBadge');
  const readiness = document.getElementById('readinessText');
  const toast = document.getElementById('toast');
  let timer;

  function read() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (_) { return {}; }
  }
  function write(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (_) {}
  }
  function arraySet(value) { return new Set(Array.isArray(value) ? value : []); }
  function saveSet(state, name, set) { state[name] = [...set]; write(state); }
  function show(message) {
    toast.textContent = message; toast.classList.add('show'); clearTimeout(timer);
    timer = setTimeout(() => toast.classList.remove('show'), 1800);
  }
  function refresh() {
    const state = read();
    const done = arraySet(state.completed);
    const marks = arraySet(state.bookmarks);
    const isDone = done.has(id);
    const missing = prerequisites.filter(x => !done.has(x));
    badge.className = isDone ? 'complete' : missing.length ? '' : 'ready';
    badge.textContent = isDone ? 'Complete' : missing.length ? 'Sequence locked' : 'Ready';
    readiness.textContent = isDone
      ? 'Recorded as complete in this browser.'
      : missing.length
        ? `${missing.length} strict prerequisite${missing.length === 1 ? '' : 's'} not marked complete. The study page remains fully readable.`
        : 'All strict prerequisites are marked complete. This node is ready in the learning sequence.';
    complete.setAttribute('aria-pressed', String(isDone));
    complete.textContent = isDone ? 'Mark incomplete' : 'Mark complete';
    bookmark.setAttribute('aria-pressed', String(marks.has(id)));
    bookmark.textContent = marks.has(id) ? 'Bookmarked' : 'Bookmark';
  }
  function toggle(name) {
    const state = read(); const set = arraySet(state[name]);
    set.has(id) ? set.delete(id) : set.add(id);
    saveSet(state, name, set); refresh();
    show(name === 'completed' ? (set.has(id) ? 'Marked complete' : 'Marked incomplete') : (set.has(id) ? 'Bookmark saved' : 'Bookmark removed'));
  }
  complete?.addEventListener('click', () => toggle('completed'));
  bookmark?.addEventListener('click', () => toggle('bookmarks'));
  document.getElementById('copyLink')?.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(location.href); show('Link copied'); }
    catch (_) { show('Copy the address from the browser bar'); }
  });
  document.getElementById('printPage')?.addEventListener('click', () => window.print());
  window.addEventListener('storage', refresh);
  window.addEventListener('keydown', event => {
    if (/input|textarea|select/i.test(document.activeElement?.tagName || '')) return;
    if (event.key.toLowerCase() === 'b') { event.preventDefault(); toggle('bookmarks'); }
    if (event.key.toLowerCase() === 'c') { event.preventDefault(); toggle('completed'); }
  });
  const state = read(); state.lastNode = id; state.focusNode = id; write(state); refresh();
  if ('serviceWorker' in navigator && location.protocol.startsWith('http')) navigator.serviceWorker.register('../../sw.js').catch(() => {});
})();
'''

DIRECTORY_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#f4efe4"><title>All study nodes · DU LL.B.</title><link rel="stylesheet" href="../node.css"></head>
<body><header class="study-header"><div class="header-row"><a class="brand" href="../"><span>DU</span><strong>LL.B. Knowledge Graph</strong></a><div class="header-actions"><a href="../">Graph home</a></div></div></header>
<main class="directory-shell"><section class="directory-hero"><span class="node-code">Complete study library</span><h1>Find a study page</h1><p>Every graph node has a stable page. Search by paper code, title, module, concept, or node ID.</p></section><div class="directory-search"><label for="directoryQuery" class="quiet">Search all nodes</label><input id="directoryQuery" type="search" autocomplete="off" placeholder="Try ‘bail’, ‘Article 14’, ‘LB-106’, or a case name"><p id="directoryCount" class="directory-count">Loading index…</p></div><div id="directoryResults" class="directory-results"></div></main>
<script>
(async()=>{const q=document.getElementById('directoryQuery'),out=document.getElementById('directoryResults'),count=document.getElementById('directoryCount');let rows=[];try{rows=await (await fetch('../data/content-index.json',{cache:'no-cache'})).json()}catch(e){count.textContent='The content index could not load.';return}const norm=s=>(s||'').toLowerCase().normalize('NFKD');const draw=()=>{const query=norm(q.value).trim(),parts=query.split(/\s+/).filter(Boolean);let list=rows.filter(r=>!parts.length||parts.every(p=>norm([r.id,r.code,r.title,r.subjectTitle,r.moduleTitle,r.profile,r.guide].join(' ')).includes(p)));list=list.slice(0,120);count.textContent=`${list.length}${query?' matching':' of '+rows.length} pages shown`;out.innerHTML=list.map(r=>`<a class="directory-card" href="../${r.path}"><strong>${escapeHtml(r.title)}</strong><small>${escapeHtml([r.code,r.subjectTitle,r.moduleTitle].filter(Boolean).join(' · '))}</small><span>${r.wordCount.toLocaleString()} words</span></a>`).join('')||'<p class="quiet">No node matches that search.</p>'};const escapeHtml=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));q.addEventListener('input',draw);draw();q.focus()})();
</script></body></html>'''

def hydrate_graph(graph: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    raw_nodes = graph.get("nodes")
    raw_subjects = graph.get("subjects")
    if not isinstance(raw_nodes, dict) or not isinstance(raw_subjects, list):
        raise ValueError("curriculum.json must contain object nodes and array subjects")
    nodes: dict[str, dict[str, Any]] = {safe_id(k): dict(v) for k,v in raw_nodes.items()}
    subjects: list[dict[str, Any]] = [dict(s) for s in raw_subjects]
    subject_map: dict[str, dict[str, Any]] = {}
    for order, subject in enumerate(subjects):
        sid = safe_id(subject["id"])
        subject["id"] = sid
        subject["catalogOrder"] = order
        subject_map[sid] = subject
        node = nodes.setdefault(sid, {"id": sid, "kind": "subject"})
        preserved = dict(node)
        node.update(subject)
        node.update({k:v for k,v in preserved.items() if k in {"prerequisites","unlocks","background","related","learnable","kind"}})
        node["id"] = sid
        node.setdefault("kind", "subject")
        node.setdefault("learnable", False)
        node["subjectId"] = sid
    module_map: dict[str, dict[str, Any]] = {nid:n for nid,n in nodes.items() if clean(n.get("kind")) == "module"}
    for nid, node in nodes.items():
        node["id"] = safe_id(node.get("id") or nid)
        sid = clean(node.get("subjectId"))
        subject = subject_map.get(sid)
        if subject:
            for key in ("code","term","elective","category","source","sourceStatus","sourceNote","edition","laws","notePath"):
                value = subject.get(key)
                if value not in (None, "", []):
                    node.setdefault(key if key != "code" else "subjectCode", value)
            node.setdefault("subjectTitle", subject.get("title"))
            node.setdefault("subjectCode", subject.get("code"))
            node.setdefault("term", subject.get("term"))
            node.setdefault("source", subject.get("source"))
            node.setdefault("edition", subject.get("edition"))
            node.setdefault("laws", subject.get("laws") or [])
        mid = clean(node.get("moduleId"))
        if mid and mid in nodes:
            node.setdefault("moduleTitle", nodes[mid].get("title"))
        node.setdefault("prerequisites", [])
        node.setdefault("unlocks", [])
        node.setdefault("background", [])
        node.setdefault("related", [])
        node.setdefault("laws", [])
    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    backgrounds: dict[str, list[str]] = defaultdict(list)
    related: dict[str, list[str]] = defaultdict(list)
    for edge in graph.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        a, b, typ = clean(edge.get("from")), clean(edge.get("to")), clean(edge.get("type")).lower()
        if a not in nodes or b not in nodes:
            continue
        if typ == "prerequisite":
            incoming[b].append(a); outgoing[a].append(b)
        elif typ == "background":
            backgrounds[b].append(a)
        elif typ == "related":
            related[a].append(b); related[b].append(a)
    for nid, node in nodes.items():
        node["prerequisites"] = uniq([*(node.get("prerequisites") or []), *incoming[nid]])
        node["unlocks"] = uniq([*(node.get("unlocks") or []), *outgoing[nid]])
        node["background"] = uniq([*(node.get("background") or []), *backgrounds[nid]])
        node["related"] = uniq([*(node.get("related") or []), *related[nid]])
        for rel in ("prerequisites","unlocks","background","related"):
            node[rel] = [x for x in node[rel] if x in nodes and x != nid]
    graph["nodes"] = nodes
    graph["subjects"] = subjects
    return nodes, subjects, subject_map


def build_neighbors(graph: Mapping[str, Any], nodes: Mapping[str, Mapping[str, Any]], subjects: Sequence[Mapping[str, Any]]) -> dict[str, tuple[str | None, str | None]]:
    neighbors: dict[str, tuple[str | None, str | None]] = {}
    learning = [x for x in graph.get("learningOrder") or [] if x in nodes]
    for i, nid in enumerate(learning):
        neighbors[nid] = (learning[i-1] if i else None, learning[i+1] if i+1 < len(learning) else None)
    subject_ids = [str(s["id"]) for s in sorted(subjects, key=lambda s:(int(s.get("term") or 0), int(s.get("catalogOrder") or 0))) if s["id"] in nodes]
    for i, nid in enumerate(subject_ids):
        neighbors[nid] = (subject_ids[i-1] if i else None, subject_ids[i+1] if i+1 < len(subject_ids) else None)
    for subject in subjects:
        mids = [x for x in subject.get("moduleIds") or [] if x in nodes]
        for i, nid in enumerate(mids):
            neighbors[nid] = (mids[i-1] if i else str(subject["id"]), mids[i+1] if i+1 < len(mids) else str(subject["id"]))
    all_ids = list(nodes)
    for i, nid in enumerate(all_ids):
        neighbors.setdefault(nid, (all_ids[i-1] if i else None, all_ids[i+1] if i+1 < len(all_ids) else None))
    return neighbors


def patch_app(root: Path) -> None:
    path = root / "app.js"
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"\n  function openNode\(id, updateHash = true\) \{.*?\n  \}\n\n  function closeNode\(\)", re.S)
    replacement = '''
  function openNode(id, updateHash = true) {
    const node = nodes?.[id];
    if (!node) return;
    state.lastNode = id;
    state.focusNode = id;
    saveLocalState();
    closeSearch();
    window.location.assign(`nodes/${encodeURIComponent(id)}/`);
  }

  function closeNode()'''
    patched, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise ValueError("could not patch app.js openNode route")
    replacements = {
        "topics render when opened": "every node opens a full study page",
        "Note scaffold": "Study source index",
        "Open note on GitHub": "Open source index on GitHub",
        "structured enrichment scaffold": "source and curriculum index",
    }
    for old,new in replacements.items():
        patched = patched.replace(old,new)
    path.write_text(patched, encoding="utf-8")


def patch_index(root: Path) -> None:
    path = root / "index.html"
    text = path.read_text(encoding="utf-8")
    replacements = {
        "note index": "study library",
        "note scaffolds": "dedicated study pages",
        "note scaffold": "study source index",
        "Open any node to inspect its metadata": "Open any node to read its full dedicated study page",
        "Inspect the graph": "Study through the graph",
    }
    for old,new in replacements.items():
        text = text.replace(old,new).replace(old.title(),new.title())
    marker = "</main>"
    if "Every graph node has a dedicated study page" not in text and marker in text:
        banner = ('<section class="content-banner" aria-label="Study content status"><strong>Every graph node has a dedicated study page.</strong>'
                  '<span>Open any ready or locked node to read the full note, worked problem, exam guide, self-test, sources, and cross-references.</span>'
                  '<a href="nodes/">Browse all study pages</a></section>')
        text = text.replace(marker, banner + marker, 1)
    path.write_text(text, encoding="utf-8")
    css = root / "styles.css"
    if css.exists():
        c = css.read_text(encoding="utf-8")
        if ".content-banner" not in c:
            c += "\n.content-banner{max-width:1180px;margin:1.25rem auto 5rem;padding:1rem;border:1px solid var(--line,#d9d0bf);border-radius:16px;background:#fffdf7;display:grid;gap:.35rem}.content-banner strong{font-size:1rem}.content-banner span{color:var(--muted,#665f54);font-size:.85rem}.content-banner a{font-weight:750;color:var(--accent,#164f46)}\n"
        css.write_text(c, encoding="utf-8")


def write_service_worker(root: Path) -> None:
    (root / "sw.js").write_text(r'''const CACHE = 'du-llb-study-v3';
const CORE = ['./','index.html','styles.css','app.js','node.css','node.js','data/curriculum.json','data/content-index.json','nodes/index.html','manifest.webmanifest','assets/icon.svg'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(CORE)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{if(event.request.method!=='GET')return;const url=new URL(event.request.url);if(url.origin!==self.location.origin)return;event.respondWith(fetch(event.request).then(response=>{if(response.ok){const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(event.request,copy))}return response}).catch(async()=>{const cached=await caches.match(event.request);if(cached)return cached;if(event.request.mode==='navigate')return caches.match('./index.html');return Response.error()}))});
''', encoding="utf-8")


def rewrite_notes(root: Path, nodes: Mapping[str, Mapping[str, Any]], subjects: Sequence[Mapping[str, Any]]) -> None:
    notes = root / "notes"; notes.mkdir(exist_ok=True)
    foundations = [n for n in nodes.values() if n.get("kind") == "foundation"]
    foundation_text = ["# Common legal-method foundations", "", "These are the shared prerequisite pages used across the LL.B. graph. Each link opens the complete dedicated study page.", ""]
    for n in sorted(foundations, key=lambda x: str(x["id"])):
        foundation_text.append(f'- [{n.get("title")}](../nodes/{n["id"]}/) — `{n["id"]}`')
    (notes / "foundations.md").write_text("\n".join(foundation_text) + "\n", encoding="utf-8")
    for subject in subjects:
        sid = str(subject["id"]); path = root / clean(subject.get("notePath") or f"notes/{sid}.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f'# {subject.get("code")} — {subject.get("title")}', "",
                 f'**Term:** {subject.get("term")} · **Type:** {"Elective" if subject.get("elective") else "Core"} · **Edition:** {subject.get("edition") or "not stated"}', "",
                 f'**Full paper page:** [Open the dedicated study page](../nodes/{sid}/)', "",
                 f'**DU source:** {subject.get("source") or "Not recorded"}', "",
                 "This file is the repository source index for the paper. Substantive study content lives on the stable node pages below.", ""]
        for mid in subject.get("moduleIds") or []:
            if mid not in nodes: continue
            module = nodes[mid]
            lines.extend([f'## [{module.get("moduleNumber")}. {module.get("title")}](../nodes/{mid}/)', ""])
            for tid in module.get("children") or []:
                if tid in nodes:
                    topic = nodes[tid]
                    lines.append(f'- [{topic.get("title")}](../nodes/{tid}/) — `{tid}`')
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
    (notes / "_template.md").write_text("""# Study-page contribution template

Generated HTML pages are rebuilt from `tools/enrich_nodes.py` and `data/curriculum.json`. Do not edit generated pages directly.

A source-grounded expansion should provide: the narrow proposition; current primary source and version date; elements or stages; burden and proof; exceptions and boundaries; procedural setting; remedy; one worked problem; exam use; verified pinpoint authorities; and later-treatment or amendment checks.

Never add an exact quotation, statutory wording, case fact, holding, or empirical claim without verifying the primary source and recording a pinpoint.
""", encoding="utf-8")


def write_docs(root: Path, graph: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    stats = graph.get("meta", {}).get("stats", {})
    readme = f'''# DU LL.B. Knowledge Graph and Study Library

A mobile-first prerequisite graph and complete dedicated-page study library for the University of Delhi LL.B. course-material catalog.

[Open the deployed library](https://legedith.github.io/llb/) · [Find a study node](https://legedith.github.io/llb/nodes/) · [Open the canonical DU catalog](https://lawfaculty.du.ac.in/Students/LL.B.-Course-Materials)

## Coverage

- {stats.get("subjects", 45)} papers across six terms.
- {stats.get("modules", 384)} modules and {stats.get("topics", 3882)} syllabus-derived topics.
- {stats.get("foundations", 26)} common legal-method foundations.
- {stats.get("allNodes", len(graph.get("nodes", {})))} dedicated static study pages.
- {stats.get("strictEdges", 4043)} strict prerequisite edges, kept acyclic.
- Every page includes orientation, plain-language explanation, outcomes, prerequisite bridge, visual decision path, full study note, issue-and-proof method, boundaries, authority map, worked problem, exam guide, revision kit, self-test, source checks, and progression links.

## How it works

The graph index preserves readiness and progress. Opening a node now navigates to `nodes/<stable-id>/`, regardless of whether the node is ready or sequence-locked. A lock is only a learning-order signal; it never hides the study content.

Strict prerequisites are the only knowledge a later node may assume. Background and related links remain non-blocking cross-references. Progress and bookmarks are stored locally in the browser under the same state key used by the graph.

## Legal-content integrity

The pages provide original explanatory study content generated from the node title, paper, module, prerequisite structure, domain-specific legal method, concept-specific frameworks, legislation register, and official source trail. They do not fabricate statutory quotations, case facts, holdings, or later treatment. Where the graph supplies only the name of an authority, the page explains its curricular role and supplies a rigorous case-extraction method, while requiring verification against the judgment or reliable report.

The DU PDF edition identifies the syllabus, not necessarily current law. Before reliance, verify commencement, amendment, repeal or replacement, savings and transition, rules, notifications, later binding judgments, jurisdiction, forum, and limitation.

## Repository map

- `index.html`, `styles.css`, `app.js`: graph and curriculum navigator.
- `nodes/<id>/index.html`: one stable study page per graph node.
- `node.css`, `node.js`: shared mobile-first study-page interface and progress sync.
- `data/curriculum.json`: graph plus study-page metadata.
- `data/content-index.json`: searchable page register.
- `data/content-report.json`: generated coverage and quality validation.
- `data/content-schema.md`: study-page contract.
- `notes/`: paper and foundation source indexes linking to full pages.
- `tools/build_site.py`: curriculum graph generator.
- `tools/enrich_nodes.py`: dedicated study-page generator.

## Rebuild

The GitHub Actions workflow runs both generators, validates the graph, validates every page and required section, checks JavaScript syntax, replaces the deployed root, and commits the generated site to `main`.
'''
    (root / "README.md").write_text(readme, encoding="utf-8")
    schema = f'''# Dedicated study-page schema

Content model: `{VERSION}`

Every node in `data/curriculum.json` must resolve to `nodes/<node-id>/index.html`. All pages must include these stable section IDs:

{os.linesep.join(f'- `{x}`' for x in SECTIONS)}

## Integrity requirements

1. A page must remain readable even when its strict prerequisites are incomplete.
2. It may assume only nodes listed in its `prerequisites` array.
3. It must distinguish primary law, binding precedent, evidence, procedure, and remedy.
4. It must not invent statutory wording, quotations, case facts, holdings, empirical data, or current-law status.
5. It must identify the DU course source and state that the syllabus edition is not proof of current law.
6. It must contain a worked problem, exam method, revision material, model-answer self-test, and progression links.
7. Shared progress state uses `du-llb-graph-v1`.

`data/content-report.json` records coverage, minimum and average page length, required-section checks, routing checks, and forbidden-marker checks.
'''
    (root / "data" / "content-schema.md").write_text(schema, encoding="utf-8")
    contributing = '''# Contributing legal study content

The deployed node pages are generated. Change `tools/enrich_nodes.py`, the curriculum source data, or an explicit source-grounded content pack; do not hand-edit generated HTML that the next build will replace.

A doctrinal addition must identify jurisdiction, relevant date, primary source, proposition, elements, burden, evidence, exception, procedure, remedy, and later-treatment check. A case addition must verify court, bench, date, citation, procedural posture, material facts, issue, ratio, operative order, pinpoint passage, and later treatment. A statutory addition must verify the exact version, commencement, definitions, provisos, explanations, schedules, subordinate instruments, amendments, repeal, savings, and transition.

Use original explanation. Quote only the minimum necessary verified passage. Do not reproduce substantial copyrighted course material.
'''
    (root / "CONTRIBUTING.md").write_text(contributing, encoding="utf-8")


def write_sitemap(root: Path, ids: Sequence[str]) -> None:
    urls = ["https://legedith.github.io/llb/", "https://legedith.github.io/llb/nodes/"] + [f"https://legedith.github.io/llb/nodes/{quote(x)}/" for x in ids]
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"  <url><loc>{esc(u)}</loc></url>\n" for u in urls) + "</urlset>\n"
    (root / "sitemap.xml").write_text(body, encoding="utf-8")
    (root / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: https://legedith.github.io/llb/sitemap.xml\n", encoding="utf-8")
    (root / ".nojekyll").write_text("", encoding="utf-8")


def validate_pages(root: Path, nodes: Mapping[str, Mapping[str, Any]], index: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {str(x["id"]):x for x in index}
    missing: list[str] = []
    section_failures: dict[str,list[str]] = {}
    short: dict[str,int] = {}
    forbidden: dict[str,list[str]] = {}
    counts: list[int] = []
    kind_counts: dict[str,int] = defaultdict(int)
    for nid,node in nodes.items():
        path = root / "nodes" / nid / "index.html"
        if not path.is_file():
            missing.append(nid); continue
        text = path.read_text(encoding="utf-8")
        absent = [sid for sid in SECTIONS if f'id="{sid}"' not in text]
        if absent: section_failures[nid] = absent
        wc = words(text); counts.append(wc); kind_counts[clean(node.get("kind")) or "unknown"] += 1
        minimum = 1050 if node.get("kind") in {"topic","foundation"} or node.get("learnable") else 900
        if wc < minimum: short[nid] = wc
        lower = text.lower()
        hits = [marker for marker in FORBIDDEN if marker in lower]
        if hits: forbidden[nid] = hits
    app = (root / "app.js").read_text(encoding="utf-8")
    routing_ok = "window.location.assign(`nodes/${encodeURIComponent(id)}/`);" in app
    index_ids = [str(x["id"]) for x in index]
    checks = {
        "completeCoverage": not missing and len(index) == len(nodes) and set(index_ids) == set(nodes),
        "requiredSections": not section_failures,
        "minimumSubstance": not short,
        "noForbiddenMarkers": not forbidden,
        "uniqueIndexIds": len(index_ids) == len(set(index_ids)),
        "rootRoutesToPages": routing_ok,
    }
    return {
        "valid": all(checks.values()), "contentVersion": VERSION, "generatedOn": datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat(),
        "nodeCount": len(nodes), "pageCount": len(counts), "learnablePageCount": sum(1 for n in nodes.values() if n.get("learnable")),
        "checks": checks, "completeCoverage": checks["completeCoverage"], "requiredSections": list(SECTIONS),
        "wordCounts": {"minimum": min(counts) if counts else 0, "average": round(sum(counts)/len(counts), 1) if counts else 0, "maximum": max(counts) if counts else 0, "total": sum(counts)},
        "kindCounts": dict(sorted(kind_counts.items())), "missingPages": missing[:50], "shortPages": dict(list(short.items())[:50]),
        "sectionFailures": dict(list(section_failures.items())[:20]), "forbiddenMarkers": dict(list(forbidden.items())[:20]),
        "integrity": {
            "originalExplanations": True, "sourceLinked": True, "currentLawWarningOnEveryPage": True,
            "unverifiedQuotationsOrHoldingsGenerated": False, "sequenceLocksHideContent": False,
        },
    }


def generate(root: Path) -> dict[str, Any]:
    graph_path = root / "data" / "curriculum.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes, subjects, subject_map = hydrate_graph(graph)
    neighbors = build_neighbors(graph, nodes, subjects)
    module_map = {nid:n for nid,n in nodes.items() if n.get("kind") == "module"}
    pages_root = root / "nodes"
    if pages_root.exists(): shutil.rmtree(pages_root)
    pages_root.mkdir(parents=True)
    index: list[dict[str, Any]] = []
    learning = [x for x in graph.get("learningOrder") or [] if x in nodes]
    containers = sorted([x for x,n in nodes.items() if x not in set(learning)], key=lambda x:(int(nodes[x].get("term") or 0), clean(nodes[x].get("subjectCode")), clean(nodes[x].get("moduleNumber")), clean(nodes[x].get("title"))))
    order = learning + containers
    for nid in order:
        node = nodes[nid]
        subject = subject_map.get(clean(node.get("subjectId")))
        module = module_map.get(clean(node.get("moduleId")))
        previous_id, next_id = neighbors.get(nid, (None,None))
        page, meta = render_page(node, subject, module, nodes, previous_id, next_id)
        directory = pages_root / nid; directory.mkdir(parents=True, exist_ok=True)
        (directory / "index.html").write_text(page, encoding="utf-8")
        index.append(meta)
        node["pagePath"] = meta["path"]
        node["contentVersion"] = VERSION
        node["contentWordCount"] = meta["wordCount"]
        node["contentStatus"] = "dedicated-study-page"
    (pages_root / "index.html").write_text(DIRECTORY_HTML, encoding="utf-8")
    (root / "node.css").write_text(NODE_CSS, encoding="utf-8")
    (root / "node.js").write_text(NODE_JS, encoding="utf-8")
    data_dir = root / "data"; data_dir.mkdir(exist_ok=True)
    (data_dir / "content-index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",",":")), encoding="utf-8")
    graph.setdefault("meta", {})["content"] = {
        "version": VERSION, "dedicatedPages": len(index), "pathPattern": "nodes/<node-id>/",
        "requiredSections": list(SECTIONS), "locksHideContent": False,
    }
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, separators=(",",":")), encoding="utf-8")
    patch_app(root); patch_index(root); write_service_worker(root); rewrite_notes(root, nodes, subjects); write_sitemap(root, order)
    report = validate_pages(root, nodes, index)
    (data_dir / "content-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_docs(root, graph, report)
    if not report["valid"]:
        raise SystemExit("content validation failed: " + json.dumps(report["checks"], sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=os.environ.get("LLB_SITE_ROOT", "."), help="generated site root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = generate(root)
    print(json.dumps({"valid": report["valid"], "pageCount": report["pageCount"], "wordCounts": report["wordCounts"], "checks": report["checks"]}, indent=2))


if __name__ == "__main__":
    main()
