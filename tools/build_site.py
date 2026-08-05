from __future__ import annotations

import json
import os
import re
import shutil
import textwrap
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

# The workflow sets LLB_SITE_ROOT to a clean staging directory. Locally, the
# generator defaults to a sibling `site` directory so it never edits the source.
ROOT = Path(os.environ.get('LLB_SITE_ROOT', str(Path(__file__).resolve().parent / 'site'))).resolve()
REPO = 'Legedith/llb'
CATALOG_URL = 'https://lawfaculty.du.ac.in/Students/LL.B.-Course-Materials'


def M(title: str, items: list[str], *, summary: str = '', tags: list[str] | None = None) -> dict[str, Any]:
    return {'title': title, 'items': items, 'summary': summary, 'tags': tags or []}


def S(code: str, term: int, title: str, modules: list[dict[str, Any]], *,
      elective: bool = False, edition: str = '', source: str = '', source_status: str = 'official',
      source_note: str = '', aliases: list[str] | None = None, laws: list[str] | None = None,
      prereq: list[str] | None = None, background: list[str] | None = None,
      related: list[str] | None = None, category: str = '', catalog_code: str | None = None) -> dict[str, Any]:
    return {
        'id': code.lower(), 'code': code.upper(), 'catalogCode': catalog_code or code.upper(),
        'term': term, 'title': title, 'modules': modules, 'elective': elective,
        'edition': edition, 'source': source, 'sourceStatus': source_status,
        'sourceNote': source_note, 'aliases': aliases or [], 'laws': laws or [],
        'prereq': prereq or [], 'background': background or [], 'related': related or [],
        'category': category,
    }


FOUNDATIONS = [
    {
        'id': 'f01', 'title': 'What law does', 'kind': 'foundation',
        'summary': 'Law supplies public standards, institutions, procedures and remedies for organizing power and resolving disputes.',
        'eli15': 'Think of law as a shared rulebook plus referees, proof rules and ways to fix a wrong.',
        'prerequisites': [], 'tags': ['legal method', 'orientation']
    },
    {
        'id': 'f02', 'title': 'Facts, law, evidence and argument', 'kind': 'foundation',
        'summary': 'Separate what happened, the rule that governs it, the material that can prove it, and the reason offered for a result.',
        'eli15': 'A fact is the event, evidence is how you show it, law is the rule, and argument connects them.',
        'prerequisites': ['f01'], 'tags': ['analysis', 'evidence']
    },
    {
        'id': 'f03', 'title': 'Public law, private law, civil law and criminal law', 'kind': 'foundation',
        'summary': 'These classifications identify who is acting, whose interests are protected, the process used and the possible consequences.',
        'eli15': 'Ask who is fighting whom, why the state is involved, and what can happen at the end.',
        'prerequisites': ['f02'], 'tags': ['classification']
    },
    {
        'id': 'f04', 'title': 'Legal actors and institutions', 'kind': 'foundation',
        'summary': 'Map legislatures, executives, courts, tribunals, police, regulators, lawyers, parties, witnesses and enforcement officers.',
        'eli15': 'Every legal problem has players. First learn who can make, apply, challenge and enforce a rule.',
        'prerequisites': ['f03'], 'tags': ['institutions']
    },
    {
        'id': 'f05', 'title': 'Sources and hierarchy of authority', 'kind': 'foundation',
        'summary': 'Distinguish constitutions, statutes, delegated legislation, precedent, custom, treaties, soft law and persuasive material.',
        'eli15': 'Not every rule has the same rank. A lower rule cannot normally defeat a higher one.',
        'prerequisites': ['f04'], 'tags': ['sources', 'authority']
    },
    {
        'id': 'f06', 'title': 'Anatomy of a statute', 'kind': 'skill',
        'summary': 'Read title, purpose, extent, commencement, definitions, operative rules, provisos, explanations, schedules and amendment history.',
        'eli15': 'A statute is engineered. Its definitions and exceptions can change what an ordinary word means.',
        'prerequisites': ['f05'], 'tags': ['statutory reading']
    },
    {
        'id': 'f07', 'title': 'Anatomy of a judgment', 'kind': 'skill',
        'summary': 'Identify court, posture, material facts, issues, holdings, reasons, orders, separate opinions and later treatment.',
        'eli15': 'The important part is not who won alone, but the rule the court used and why.',
        'prerequisites': ['f05'], 'tags': ['case reading']
    },
    {
        'id': 'f08', 'title': 'Ratio, obiter and precedent', 'kind': 'foundation',
        'summary': 'Work out what proposition was necessary to decide the case, what was additional, and how court hierarchy affects force.',
        'eli15': 'A case is binding for the rule needed to decide it, not every sentence in the judgment.',
        'prerequisites': ['f07'], 'tags': ['precedent']
    },
    {
        'id': 'f09', 'title': 'Jurisdiction, forum and maintainability', 'kind': 'foundation',
        'summary': 'Before merits, ask whether the decision-maker has territorial, subject, personal and procedural authority to act.',
        'eli15': 'Even a strong claim can fail in the wrong court or through the wrong procedure.',
        'prerequisites': ['f04', 'f05'], 'tags': ['procedure', 'jurisdiction']
    },
    {
        'id': 'f10', 'title': 'Legal persons, status and capacity', 'kind': 'foundation',
        'summary': 'Law attributes rights, duties, powers and disabilities to natural persons, groups, corporations, states and institutions.',
        'eli15': 'Law decides who counts as a legal person and what each person is allowed to do.',
        'prerequisites': ['f03', 'f05'], 'tags': ['personhood', 'capacity']
    },
    {
        'id': 'f11', 'title': 'Rights, duties, powers, liberties and liabilities', 'kind': 'foundation',
        'summary': 'Use Hohfeldian relations to avoid treating every legal advantage as the same kind of right.',
        'eli15': 'Your right may mean someone owes you a duty, or simply that you are free to act. Those are different.',
        'prerequisites': ['f10'], 'tags': ['jurisprudence']
    },
    {
        'id': 'f12', 'title': 'Elements, tests, exceptions and defences', 'kind': 'skill',
        'summary': 'Turn a doctrine into a checklist, then identify exclusions, burdens, standards and consequences for each element.',
        'eli15': 'Most legal rules work like a recipe: required ingredients, special exceptions and a result.',
        'prerequisites': ['f06', 'f07', 'f11'], 'tags': ['issue spotting']
    },
    {
        'id': 'f13', 'title': 'Burdens, standards and presumptions', 'kind': 'foundation',
        'summary': 'Distinguish legal and evidential burdens, standards of proof, rebuttable presumptions and adverse inferences.',
        'eli15': 'Ask who must prove what, how convincing the proof must be, and what the law assumes at the start.',
        'prerequisites': ['f02', 'f12'], 'tags': ['proof']
    },
    {
        'id': 'f14', 'title': 'Lifecycle of a legal dispute', 'kind': 'foundation',
        'summary': 'Trace intake, cause of action or offence, forum, pleadings or charge, interim relief, proof, decision, appeal and enforcement.',
        'eli15': 'A dispute moves through stages. A rule can matter at one stage and be irrelevant at another.',
        'prerequisites': ['f09', 'f12', 'f13'], 'tags': ['procedure']
    },
    {
        'id': 'f15', 'title': 'Remedies and enforcement', 'kind': 'foundation',
        'summary': 'Compare compensation, restitution, injunction, declaration, specific performance, punishment, judicial review and institutional orders.',
        'eli15': 'Winning means little unless the legal system can give and enforce the right kind of fix.',
        'prerequisites': ['f11', 'f14'], 'tags': ['remedies']
    },
    {
        'id': 'f16', 'title': 'Interpretation and legal reasoning', 'kind': 'skill',
        'summary': 'Use text, context, purpose, precedent, principle, analogy and consequence while respecting institutional limits.',
        'eli15': 'Legal reading is not guessing what feels fair; it is giving reasons that fit the legal materials.',
        'prerequisites': ['f06', 'f08', 'f12'], 'tags': ['interpretation']
    },
    {
        'id': 'f17', 'title': 'Fact chronology and issue tree', 'kind': 'skill',
        'summary': 'Build a dated fact map, identify disputed facts, and decompose the legal question into nested issues.',
        'eli15': 'Put events in order, then turn one big problem into smaller questions you can answer.',
        'prerequisites': ['f02', 'f12'], 'tags': ['analysis']
    },
    {
        'id': 'f18', 'title': 'Legal research and source verification', 'kind': 'skill',
        'summary': 'Move from secondary orientation to primary authority, verify currency, history, jurisdiction and later treatment.',
        'eli15': 'Do not stop at the first summary. Find the real rule, check that it is current, and see whether later law changed it.',
        'prerequisites': ['f05', 'f06', 'f07'], 'tags': ['research']
    },
    {
        'id': 'f19', 'title': 'Rule synthesis and IRAC', 'kind': 'skill',
        'summary': 'Synthesize multiple authorities into a usable rule and apply it to each material fact before reaching a conclusion.',
        'eli15': 'State the question, give the rule, connect each fact to the rule, and then answer.',
        'prerequisites': ['f08', 'f12', 'f17', 'f18'], 'tags': ['writing', 'analysis']
    },
    {
        'id': 'f20', 'title': 'Legal writing and citation', 'kind': 'skill',
        'summary': 'Write propositions with authority, distinguish fact from inference, use headings, and cite sources so a reader can verify them.',
        'eli15': 'Make each important claim easy to understand and easy to check.',
        'prerequisites': ['f19'], 'tags': ['writing', 'citation']
    },
    {
        'id': 'f21', 'title': 'Client interviewing and counselling', 'kind': 'skill',
        'summary': 'Elicit facts without leading, explain options and risk, identify objectives, obtain instructions and preserve confidentiality.',
        'eli15': 'Listen first, ask clear questions, explain choices honestly, and let the client decide.',
        'prerequisites': ['f17', 'f20'], 'tags': ['client skills']
    },
    {
        'id': 'f22', 'title': 'Negotiation and settlement thinking', 'kind': 'skill',
        'summary': 'Separate positions from interests, assess alternatives, generate options and test enforceable settlement terms.',
        'eli15': 'Work out what each side really needs and what happens if no deal is made.',
        'prerequisites': ['f15', 'f21'], 'tags': ['negotiation']
    },
    {
        'id': 'f23', 'title': 'Drafting rules and instruments', 'kind': 'skill',
        'summary': 'Draft for legal effect, defined terms, conditions, allocation of risk, procedure, remedies and predictable interpretation.',
        'eli15': 'Good drafting tells people exactly who must do what, when, and what happens if they do not.',
        'prerequisites': ['f06', 'f16', 'f20'], 'tags': ['drafting']
    },
    {
        'id': 'f24', 'title': 'Oral advocacy and response', 'kind': 'skill',
        'summary': 'Lead with the requested order and decisive issue, answer the question asked, use the record, and concede safely where needed.',
        'eli15': 'Tell the decision-maker what you need, why the law permits it, and where the facts prove it.',
        'prerequisites': ['f19', 'f20'], 'tags': ['advocacy']
    },
    {
        'id': 'f25', 'title': 'Professional responsibility and confidentiality', 'kind': 'foundation',
        'summary': 'Identify duties to client, court, opponent, profession and public; manage conflicts, candour, competence, money and confidential information.',
        'eli15': 'A lawyer serves a client but cannot lie to the court, misuse trust or ignore conflicts.',
        'prerequisites': ['f04', 'f11', 'f21'], 'tags': ['ethics']
    },
    {
        'id': 'f26', 'title': 'Current-law and edition check', 'kind': 'skill',
        'summary': 'Check commencement, amendments, repeals, replacement codes, rules, notifications and binding decisions as of the research date.',
        'eli15': 'A perfect note on old law is still wrong today. Always check what is now in force.',
        'prerequisites': ['f18', 'f20'], 'tags': ['currency', 'verification']
    },
]

SUBJECTS: list[dict[str, Any]] = []

# Term I ----------------------------------------------------------------------
SUBJECTS += [
S('LB-106', 1, 'Jurisprudence I (Legal Method)', [
    M('Evolution of Bharatiya jurisprudence I', [
        'Environmental consciousness in Vedic thought',
        'Dharma as an ordering idea',
        'Dharmashastras and Smritis as legal sources',
        'Codification and transmission of ancient norms',
        'Dispute resolution in ancient India',
        'Continuity and limits of using ancient sources today',
    ]),
    M('Evolution of Bharatiya jurisprudence II', [
        'Ṛta, dharma and kartavya',
        'Kautilya on state, punishment and administration',
        'Law and justice in the Mahabharata',
        'Ramarajya as an ideal of governance',
        'Comparing duty-centred and right-centred legal thought',
    ]),
    M('Major legal systems', [
        'Common-law method',
        'Civil-law method',
        'Hybrid and mixed legal systems',
        'Islamic legal traditions',
        'Socialist legal traditions',
        'Ancient Indian legal traditions',
        'How legal families affect sources, procedure and judging',
    ]),
    M('The Indian legal system', [
        'Constitutional identity and the Preamble',
        'Court hierarchy and territorial structure',
        'Original, appellate, advisory and supervisory jurisdiction',
        'Tribunals and specialist adjudication',
        'Legal aid and access to justice',
        'The legal profession and the Advocates Act, 1961',
        'Institutions that make, apply and enforce law',
    ]),
    M('Sources of law', [
        'Dharma as a source of normativity',
        'Custom and the tests of a valid custom',
        'Judicial precedent and stare decisis',
        'Ratio decidendi and obiter dicta',
        'Legislation and delegated legislation',
        'Conflicts between sources and hierarchy rules',
    ]),
    M('Analytical and positivist jurisprudence', [
        'John Austin and law as command',
        'Sovereignty, sanctions and habitual obedience',
        'H. L. A. Hart: primary and secondary rules',
        'Rule of recognition, change and adjudication',
        'Internal and external points of view',
        'Hans Kelsen and the pure theory of law',
        'Grundnorm and hierarchy of norms',
        'Limits of positivism',
    ]),
    M('Natural, historical and sociological approaches', [
        'Natural law and the relation between law and morality',
        'Lon Fuller and the internal morality of law',
        'The Hart–Fuller debate',
        'Savigny and the historical school',
        'Volksgeist, custom and legal development',
        'Roscoe Pound and sociological jurisprudence',
        'Law as social engineering',
        'Balancing interests and contemporary critique',
    ]),
], edition='2025 revised', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/JURISPRUDENCE-ILegalMethodCourseCode_LB-1061stsemesterLLB.pdf',
   laws=['Constitution of India', 'Advocates Act, 1961'], prereq=['f01','f02','f04','f05','f07'],
   category='Legal method and theory'),

S('LB-102', 1, 'Principles of Contract', [
    M('Nature and history of contractual obligation', [
        'Promise, agreement and contract',
        'Why law enforces some promises',
        'Freedom of contract and its limits',
        'Contract, status and market exchange',
        'Civil obligations arising outside contract',
        'The structure of the Indian Contract Act, 1872',
    ]),
    M('Formation of agreement', [
        'Intention to create legal relations',
        'Offer and proposal',
        'Invitation to offer',
        'General, specific, standing and cross offers',
        'Communication of offer',
        'Acceptance and the mirror-image rule',
        'Modes of acceptance',
        'Communication of acceptance',
        'Revocation of offer and acceptance',
        'Postal and instantaneous communications',
    ]),
    M('Tenders and auctions', [
        'Tender as invitation or standing offer',
        'Acceptance of a tender and individual orders',
        'Withdrawal and blacklisting concerns',
        'Auction notices and reserve prices',
        'Completion of sale at auction',
        'Online and electronic auctions',
    ]),
    M('Consideration and privity', [
        'Meaning and function of consideration',
        'Consideration at the desire of the promisor',
        'Past, present and future consideration',
        'Adequacy and reality of consideration',
        'Privity of contract',
        'Privity of consideration in Indian law',
        'Beneficiaries, trusts and family arrangements',
        'Acknowledgment, agency, assignment and statutory exceptions',
        'Agreements without consideration and statutory exceptions',
    ]),
    M('Capacity to contract', [
        'Age of majority and minor agreements',
        'Voidness of a minor’s agreement',
        'Beneficial contracts for minors',
        'Restitution against minors',
        'Liability for necessaries',
        'Ratification after majority',
        'Soundness of mind',
        'Persons disqualified by law',
    ]),
    M('Free consent', [
        'Consent and consensus ad idem',
        'Coercion',
        'Undue influence and relationships of dominance',
        'Fraud and active concealment',
        'Misrepresentation',
        'Silence and duties to disclose',
        'Mistake of fact',
        'Mistake of law',
        'Unilateral and bilateral mistake',
        'Voidability, rescission and restitution',
    ]),
    M('Legality and limits on freedom of contract', [
        'Void and voidable agreements',
        'Unlawful object or consideration',
        'Forbidden acts and defeating the law',
        'Fraudulent, injurious and immoral objects',
        'Public policy',
        'Partial illegality and severance',
        'Restraint of marriage',
        'Restraint of trade and exceptions',
        'Restraint of legal proceedings',
        'Uncertain agreements',
        'Wagering agreements',
    ]),
    M('Discharge of contract', [
        'Performance and tender of performance',
        'Reciprocal promises and order of performance',
        'Prevention and waiver',
        'Agreement, rescission, alteration and remission',
        'Novation',
        'Initial impossibility',
        'Supervening impossibility and frustration',
        'Grounds and limits of frustration',
        'Effects of frustration and restitution',
        'Discharge by breach',
    ]),
    M('Breach and damages', [
        'Actual and anticipatory breach',
        'Expectation, reliance and restitution interests',
        'Ordinary and special damages',
        'Remoteness and contemplation of parties',
        'Causation of contractual loss',
        'Measure of damages',
        'Mitigation',
        'Certainty of loss',
        'Liquidated damages and penalty',
        'Nominal and exemplary damages',
    ]),
    M('Quasi-contractual obligations', [
        'Why quasi-contract is not a contract',
        'Necessaries supplied to an incapable person',
        'Payment by an interested person',
        'Non-gratuitous acts',
        'Finder of goods',
        'Money paid or goods delivered by mistake or coercion',
        'Unjust enrichment and restitution',
    ]),
    M('Electronic contracts', [
        'Nature and scope of e-contracts',
        'Clickwrap, browsewrap and shrinkwrap terms',
        'Electronic offer and acceptance',
        'Attribution and acknowledgment of electronic records',
        'Time and place of dispatch and receipt',
        'Electronic signatures and authentication',
        'Information Technology Act framework',
        'Consumer and intermediary concerns',
        'Judicial treatment of electronic agreements',
    ]),
], edition='2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/Ist%20Term_Law%20of%20Contract_LB102_2023.pdf',
   laws=['Indian Contract Act, 1872', 'Information Technology Act, 2000', 'Specific Relief Act, 1963'],
   prereq=['f06','f10','f11','f12','f15','@lb-106.m05'], category='Private law'),

S('LB-103', 1, 'Law of Torts', [
    M('Foundations of tortious liability', [
        'Origin and development of tort law in England',
        'Reception and development of tort law in India',
        'Meaning, function and definition of tort',
        'Constituents of tortious liability',
        'Injuria sine damno',
        'Damnum sine injuria',
        'Ubi jus ibi remedium',
        'Tort distinguished from crime, contract and breach of trust',
        'Intention, motive and malice',
        'Malice in fact and malice in law',
    ]),
    M('General defences', [
        'Consent and volenti non fit injuria',
        'Knowledge distinguished from consent',
        'Rescue cases and limits on volenti',
        'Consent obtained by fraud or compulsion',
        'Statutory authority',
        'Act of God',
        'Inevitable accident',
        'Plaintiff’s own wrongdoing',
        'Necessity and private defence',
    ]),
    M('Negligence', [
        'Theories and meaning of negligence',
        'Duty of care',
        'Neighbour principle and foreseeability',
        'Breach and the reasonable-person standard',
        'Magnitude of risk and cost of precautions',
        'Damage and actionable loss',
        'Res ipsa loquitur',
        'Contributory and composite negligence',
        'Manufacturer’s liability',
        'Professional and medical negligence',
        'Standard of care in medical treatment',
        'Informed consent and diagnostic error',
    ]),
    M('Nervous shock and psychiatric harm', [
        'Meaning of nervous shock',
        'Impact theory and its decline',
        'Reasonable foreseeability of psychiatric injury',
        'Immediate aftermath',
        'Primary victims',
        'Secondary victims',
        'Proximity of relationship, time and space',
        'Sudden shock and policy limits',
    ]),
    M('Causation and remoteness', [
        'Factual causation and the but-for test',
        'Material contribution and multiple causes',
        'Concurrent causes',
        'Consecutive causes',
        'Intervening acts',
        'Acts of third parties and claimants',
        'Directness test',
        'Reasonable foreseeability test',
        'Kind of damage and manner of occurrence',
        'Eggshell-skull rule',
    ]),
    M('No-fault, strict and absolute liability', [
        'Rationale for liability without fault',
        'Rule in Rylands v Fletcher',
        'Non-natural use, escape and dangerous thing',
        'Exceptions to strict liability',
        'Application of strict liability in India',
        'Absolute liability for hazardous industries',
        'Bhopal gas disaster and enterprise liability',
        'Public Liability Insurance Act, 1991',
        'Motor-vehicle no-fault compensation',
        'Hit-and-run compensation',
    ]),
    M('Vicarious and state liability', [
        'Basis of vicarious liability',
        'Employer–employee relationship',
        'Course of employment',
        'Authorized acts and unauthorized modes',
        'Independent contractors and exceptions',
        'State liability in tort',
        'Sovereign and non-sovereign functions',
        'Law Commission proposals',
        'Constitutional tort and public-law compensation',
    ]),
    M('Defamation', [
        'Reputation as a protected interest',
        'Libel and slander',
        'Defamatory meaning',
        'Reference to the plaintiff',
        'Publication to a third person',
        'Innuendo',
        'Truth or justification',
        'Fair comment and honest opinion',
        'Absolute and qualified privilege',
        'Consent, apology and mitigation',
        'Civil and criminal defamation compared',
    ]),
    M('Consumer protection', [
        'Evolution from the Consumer Protection Act, 1986',
        'Objects and scheme of the Consumer Protection Act, 2019',
        'Consumer, goods and services',
        'Defect, deficiency and unfair trade practice',
        'Unfair contracts',
        'Consumer rights',
        'District, State and National Commissions',
        'Jurisdiction and procedure of consumer commissions',
        'Consumer Protection Councils',
        'Central Consumer Protection Authority',
        'Misleading advertisements and endorsers',
        'E-commerce and marketplace liability',
        'Product liability',
        'Consumer mediation',
        'Appeals, limitation and enforcement',
    ]),
], edition='2025', source='https://lawfaculty.du.ac.in/userfiles/downloads/Ist%2BTerm_Law%2Bof%2BTorts_LB103_2025%28pdfgear.com%29.pdf',
   laws=['Consumer Protection Act, 2019', 'Public Liability Insurance Act, 1991', 'Motor Vehicles Act, 1988'],
   prereq=['f11','f12','f13','f15','@lb-102.m01'], background=['@lb-102'], category='Private law'),

S('LB-104', 1, 'Law of Crimes I (Bharatiya Nyaya Sanhita)', [
    M('Elements of crime', [
        'Distinction between civil and criminal liability',
        'Act, omission and prohibited consequence',
        'Mens rea and fault requirements',
        'Strict liability in criminal law',
        'Coincidence of actus reus and mens rea',
        'Causation in criminal liability',
        'Types of punishment under the BNS',
        'Death penalty',
        'Community service',
        'Sentencing proportionality and individualized justice',
    ]),
    M('General exceptions', [
        'Structure and burden of general exceptions',
        'Unsoundness of mind',
        'Cognitive incapacity and legal insanity',
        'Intoxication: voluntary and involuntary',
        'Private defence of body',
        'Private defence of property',
        'Necessity and proportionality in private defence',
        'Commencement and continuation of the right',
        'Exceeding private defence',
    ]),
    M('Inchoate crimes', [
        'Meaning and grades of incomplete offending',
        'Abetment by instigation',
        'Abetment by conspiracy',
        'Abetment by intentional aid',
        'Criminal conspiracy as a substantive offence',
        'Agreement and overt act',
        'Preparation distinguished from attempt',
        'Tests for attempt',
        'Impossibility and abandonment',
        'Attempt to suicide and abetment concerns',
    ]),
    M('Joint and group liability', [
        'Common intention',
        'Participation and prior meeting of minds',
        'Development of common intention during occurrence',
        'Common object',
        'Unlawful assembly',
        'Membership and constructive liability',
        'Common intention compared with common object',
        'Proof of group liability',
    ]),
    M('Offences against women', [
        'Rape: ingredients and consent',
        'Aggravated forms and sentencing',
        'Gang rape and repeat offending',
        'Disclosure of victim identity and reporting restrictions',
        'Sexual harassment',
        'Assault or criminal force with sexual or disrobing intent',
        'Voyeurism',
        'Stalking',
        'Words or gestures insulting modesty',
        'Offences relating to marriage',
        'Cruelty, dowry death and related offences',
    ]),
    M('Offences affecting life I', [
        'Culpable homicide',
        'Murder',
        'Intention and knowledge',
        'Distinguishing culpable homicide from murder',
        'Murder exceptions',
        'Grave and sudden provocation',
        'Sudden fight',
        'Transferred malice and mistaken victim',
        'Mob lynching',
        'Causation of death',
    ]),
    M('Offences affecting life II and organized violence', [
        'Causing death by negligence',
        'Gross negligence and criminal threshold',
        'Medical and road-traffic negligence',
        'Organized crime',
        'Continuing unlawful activity and syndicates',
        'Petty organized crime',
        'Terrorist act',
        'Overlap with special security legislation',
    ]),
    M('Crimes against children, the body and the state', [
        'Kidnapping from lawful guardianship',
        'Abduction',
        'Kidnapping distinguished from abduction',
        'Trafficking in persons',
        'Exploitation and consent in trafficking',
        'Hiring or employing a child to commit an offence',
        'Selling or buying a child for prostitution',
        'Acts endangering sovereignty, unity and integrity of India',
        'Speech, incitement and constitutional limits',
    ]),
    M('Offences against property I', [
        'Movable property and dishonest intention',
        'Theft',
        'Moving property and possession',
        'Snatching',
        'Extortion',
        'Robbery by theft or extortion',
        'Dacoity',
        'Preparation and assembly for dacoity',
        'Receiving property connected with dacoity',
    ]),
    M('Offences against property II', [
        'Criminal misappropriation',
        'Finding property and dishonest conversion',
        'Criminal breach of trust',
        'Entrustment and dominion',
        'Aggravated breach of trust',
        'Cheating',
        'Deception, inducement and delivery of property',
        'Cheating by personation',
        'Distinguishing cheating from breach of contract',
    ]),
], edition='2025; BNS 2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/Law%20of%20Crimes-1%20BNS%202025.pdf',
   laws=['Bharatiya Nyaya Sanhita, 2023', 'Constitution of India'],
   prereq=['f03','f11','f12','f13','f15','@lb-106.m05'], related=['@lb-103'], category='Criminal law'),

S('LB-105', 1, 'Family Law I', [
    M('Marriage under Hindu law', [
        'Concept and nature of Hindu marriage',
        'Application of the Hindu Marriage Act',
        'Conditions for a valid Hindu marriage',
        'Capacity, age and prohibited relationships',
        'Solemnisation and customary ceremonies',
        'Proof of marriage',
        'Live-in relationships and presumptions of marriage',
        'Registration of marriage',
        'Void marriages',
        'Voidable marriages',
        'Bigamy and conversion',
    ]),
    M('Matrimonial remedies under Hindu law', [
        'Restitution of conjugal rights',
        'Constitutional and autonomy critiques of restitution',
        'Judicial separation',
        'Theories of divorce',
        'Cruelty',
        'Desertion',
        'Conversion, mental disorder and communicable disease grounds',
        'Renunciation and presumed death',
        'Additional grounds available to the wife',
        'Mutual-consent divorce',
        'Cooling-off period and waiver',
        'Irretrievable breakdown of marriage',
        'Bars to matrimonial relief',
    ]),
    M('Maintenance under Hindu law', [
        'Interim maintenance and litigation expenses under the HMA',
        'Permanent alimony under the HMA',
        'Wife’s maintenance under HAMA',
        'Maintenance of children and aged parents',
        'Summary maintenance in criminal procedure',
        'Maintenance in live-in relationships',
        'Domestic Violence Act monetary relief',
        'Overlap, adjustment and enforcement of maintenance orders',
    ]),
    M('Adoption', [
        'Purpose and legal effects of adoption',
        'Capacity of a Hindu male to adopt',
        'Capacity of a Hindu female to adopt',
        'Persons capable of giving a child in adoption',
        'Persons capable of being adopted',
        'Conditions for a valid adoption',
        'Proof and presumption of adoption',
        'Effects on family and property relationships',
        'CARA framework and inter-country adoption',
        'Adoption through secular juvenile-justice law',
    ]),
    M('Minority and guardianship under Hindu law', [
        'Minor and guardian definitions',
        'Natural guardians',
        'Mother as natural guardian',
        'Testamentary guardians',
        'De facto guardians',
        'Powers and limits of guardians over property',
        'Welfare of the child as paramount consideration',
        'Custody distinguished from guardianship',
    ]),
    M('Sources and schools of Muslim law', [
        'Quran',
        'Sunna and hadith',
        'Ijma',
        'Qiyas',
        'Custom and legislation',
        'Judicial precedent and equity',
        'Sunni schools',
        'Shia schools',
        'Shariat Act and application of Muslim personal law',
    ]),
    M('Marriage under Muslim law', [
        'Nikah as civil contract and religious institution',
        'Proposal and acceptance',
        'Capacity and guardianship in marriage',
        'Witnesses and form',
        'Prohibited degrees and impediments',
        'Valid, void and irregular marriages',
        'Muta marriage',
        'Dower: nature and kinds',
        'Prompt and deferred dower',
        'Rights arising from marriage',
    ]),
    M('Divorce under Muslim law', [
        'Talaq and its forms',
        'Procedural and substantive limits on talaq',
        'Talaq-e-biddat and constitutional invalidity',
        'Khula',
        'Mubarat',
        'Delegated divorce',
        'Judicial divorce under the Dissolution of Muslim Marriages Act, 1939',
        'Grounds and procedure for judicial dissolution',
        'Iddat and consequences of dissolution',
    ]),
    M('Maintenance under Muslim law', [
        'Maintenance during subsistence of marriage',
        'Maintenance during iddat',
        'Fair and reasonable provision after divorce',
        'Muslim Women (Protection of Rights on Divorce) Act, 1986',
        'Summary maintenance under criminal procedure',
        'Maintenance of children',
        'Constitutional equality and personal-law questions',
    ]),
], edition='2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/Ist%20Term_Family%20Law-%20I_LB105_2023.pdf',
   laws=['Hindu Marriage Act, 1955', 'Hindu Adoptions and Maintenance Act, 1956', 'Hindu Minority and Guardianship Act, 1956', 'Dissolution of Muslim Marriages Act, 1939', 'Muslim Women (Protection of Rights on Divorce) Act, 1986', 'Protection of Women from Domestic Violence Act, 2005', 'Prohibition of Child Marriage Act, 2006'],
   prereq=['f10','f11','f12','f14','@lb-106.m04'], related=['@lb-103','@lb-104'], category='Family law'),
]

# Term II ---------------------------------------------------------------------
SUBJECTS += [
S('LB-201', 2, 'Law of Evidence (Bharatiya Sakshya Adhiniyam)', [
    M('Evidence law and the new statutory framework', [
        'Why evidence law is procedural',
        'Adversarial and inquisitorial models',
        'History from the Indian Evidence Act to the BSA',
        'Continuity and change under the Bharatiya Sakshya Adhiniyam, 2023',
        'Relationship with BNS and BNSS terminology',
        'Facts in issue and relevant facts',
        'Proved, disproved and not proved',
        'May presume, shall presume and conclusive proof',
        'Court, document and evidence definitions',
        'Judicial creativity in evidence law',
    ]),
    M('Relevancy and admissibility', [
        'Logical relevance and legal relevance',
        'Relevancy distinguished from admissibility',
        'Same transaction and res gestae',
        'Occasion, cause, effect and opportunity',
        'Motive, preparation and conduct',
        'Conspiracy and acts of co-conspirators',
        'Admissions: nature and persons who may make them',
        'Admissions by agents and persons in representative character',
        'Confessions and voluntariness',
        'Confession to police and in police custody',
        'Discovery statements',
        'Retracted and co-accused confessions',
        'Dying declarations',
        'Statements by unavailable persons',
        'Expert opinion',
        'Handwriting, fingerprint, scientific and electronic expertise',
        'Character evidence',
    ]),
    M('Proof, privilege and documentary evidence', [
        'Facts that need not be proved',
        'Judicial notice',
        'Admissions dispensing with proof',
        'Estoppel',
        'Estoppel of tenant, licensee and acceptor',
        'Privileged state communications',
        'Professional communications and legal privilege',
        'Marital communications',
        'Oral evidence and directness',
        'Primary and secondary evidence',
        'Public and private documents',
        'Certified copies and presumptions',
        'Electronic and digital records',
        'Authentication and integrity of electronic evidence',
        'Exclusion of oral evidence by documentary terms',
        'Ambiguity, surrounding circumstances and provisos',
    ]),
    M('Accomplice evidence', [
        'Accomplice competence',
        'Approver and tender of pardon',
        'Presumption about accomplice testimony',
        'Rule of prudence requiring corroboration',
        'Nature and scope of corroboration',
        'Accomplice evidence compared with co-accused confession',
    ]),
    M('Witnesses and examination', [
        'Competency and compellability',
        'Child witnesses',
        'Witness unable to communicate verbally',
        'Hostile witnesses',
        'Examination-in-chief',
        'Leading questions',
        'Cross-examination and its scope',
        'Questions testing veracity and credit',
        'Impeaching credit',
        'Contradiction by previous statements',
        'Refreshing memory',
        'Re-examination',
        'Court questions and production powers',
        'Vulnerable witnesses and protective procedure',
    ]),
    M('Presumptions and burdens', [
        'General burden of proof',
        'Burden as to particular facts',
        'Facts especially within knowledge',
        'Shifting evidential burdens',
        'Presumption of innocence',
        'Presumptions in dowry death and suicide cases',
        'Presumptions in sexual-offence cases',
        'Presumptions concerning documents and electronic records',
        'Adverse inference for withheld evidence',
        'Rebutting statutory presumptions',
    ]),
], edition='2025; BSA 2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/CM_LB201_2025.pdf',
   laws=['Bharatiya Sakshya Adhiniyam, 2023', 'Bharatiya Nagarik Suraksha Sanhita, 2023', 'Bharatiya Nyaya Sanhita, 2023', 'Information Technology Act, 2000'],
   prereq=['f02','f07','f08','f13','f14','@lb-104.m04'], related=['@lb-203'], category='Evidence and procedure'),

S('LB-202', 2, 'Family Law II', [
    M('Joint Hindu family and coparcenary', [
        'Joint Hindu family and the presumption of jointness',
        'Coparcenary distinguished from joint family',
        'Mitakshara and Dayabhaga systems',
        'Incidents of coparcenary',
        'Coparcenary property and separate property',
        'Property inherited from paternal and maternal ancestors',
        'Karta: sui generis position',
        'Karta’s powers and duties',
        'Position before the Hindu Succession Amendment Act, 2005',
        'Daughter as coparcener after 2005',
        'Sole surviving coparcener and tax characterization',
    ]),
    M('Alienation of joint family property', [
        'Limits on unilateral alienation',
        'Alienation by karta for legal necessity',
        'Benefit of estate',
        'Indispensable duties',
        'Sale and mortgage by karta',
        'Gifts by karta',
        'Wills and testamentary disposition',
        'Alienation by father',
        'Alienee’s rights, duties and remedies',
        'Pious obligation and its statutory change',
    ]),
    M('Partition', [
        'Meaning and effect of partition',
        'Severance of status',
        'Subject matter of partition',
        'Property available and unavailable for division',
        'Partition by notice, agreement, suit and conduct',
        'Persons entitled to demand partition',
        'Persons entitled to a share when partition occurs',
        'Rules for division and allotment',
        'Partial partition',
        'Reopening partition',
        'Reunion',
    ]),
    M('Hindu Succession Act: application and general rules', [
        'Scope and application of the Hindu Succession Act, 1956',
        'Intestate and testamentary succession',
        'General principles of inheritance',
        'Full-blood, half-blood and uterine relationships',
        'Mode of succession and representation',
        'Disqualifications of heirs',
        'Murderer and convert-descendant rules',
        'Rights of children from void or voidable marriages',
        'Preferential right to acquire property',
    ]),
    M('Succession to a male Hindu intestate', [
        'Devolution of Mitakshara coparcenary interest',
        'Notional partition method',
        'Class I heirs',
        'Distribution among Class I heirs',
        'Class II heirs',
        'Agnates and cognates',
        'Government escheat',
        'Separate property of a male Hindu',
        'Effect of the 2005 amendment and Vineeta Sharma',
    ]),
    M('Succession to a female Hindu intestate', [
        'General order of succession',
        'Property inherited from parents',
        'Property inherited from husband or father-in-law',
        'Source-based reversion rules',
        'Distribution among heirs',
        'Critiques of the statutory scheme',
    ]),
    M('Hindu women’s estate', [
        'Limited estate under classical Hindu law',
        'Section 14(1): enlargement into absolute ownership',
        'Section 14(2): restricted grants',
        'Pre-existing right and possession',
        'Maintenance property and absolute title',
        'Reversioners and abolition of limited estate',
    ]),
    M('Muslim law of gifts', [
        'Meaning and essentials of hiba',
        'Declaration, acceptance and delivery of possession',
        'Capacity of donor and donee',
        'Subject matter of gift',
        'Gift of mushaa',
        'Exceptions to the mushaa rule',
        'Gift during marz-ul-maut',
        'Revocation of gift',
        'Hiba-bil-iwaz and related transactions',
    ]),
    M('Muslim law of wills', [
        'Capacity to make a will',
        'Subject matter of bequest',
        'Persons who may receive a bequest',
        'One-third limitation',
        'Bequest to an heir',
        'Consent of heirs',
        'Abatement of legacies',
        'Revocation and lapse',
    ]),
    M('Muslim law of inheritance', [
        'Opening of succession and absence of birthright',
        'Sunni and Shia general rules',
        'Sharers, residuaries and distant kindred',
        'Primary heirs and exclusion',
        'Doctrine of representation and its limits',
        'Aul and radd',
        'Rules of distribution',
        'Disqualifications and impediments',
    ]),
], edition='2022', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/IInd%20Term_Family%20Law-%20II_LB202_2022%20.pdf',
   laws=['Hindu Succession Act, 1956', 'Hindu Succession (Amendment) Act, 2005', 'Indian Succession Act, 1925', 'Muslim Personal Law (Shariat) Application Act, 1937'],
   prereq=['@lb-105.m09','@lb-102.m05','f15'], related=['@lb-204'], category='Family and succession law'),

S('LB-203', 2, 'Law of Crimes II (Bharatiya Nagarik Suraksha Sanhita)', [
    M('Introduction to criminal procedure', [
        'Importance and objectives of criminal procedure',
        'BNSS compared with the Code of Criminal Procedure, 1973',
        'Use of technology and statutory timelines',
        'Stakeholders in criminal justice administration',
        'Hierarchy of criminal courts',
        'Territorial and subject jurisdiction of criminal courts',
        'Powers and duties of magistrates, sessions courts and High Courts',
        'Key BNSS definitions',
        'Cognizable and non-cognizable offences',
        'Bailable and non-bailable offences',
        'Summons and warrant cases',
    ]),
    M('Initiation of a criminal case', [
        'Information to police and registration of FIR',
        'Mandatory registration and preliminary inquiry',
        'Zero FIR and electronic information',
        'Kinds and evidentiary value of FIR',
        'Remedies for refusal to register FIR',
        'Non-cognizable reports and magistrate authorization',
        'Complaint cases before magistrates',
        'Inquest and inquiry into suspicious death',
        'Medical examination and forensic investigation',
        'Police report on completion of investigation',
    ]),
    M('Investigation, arrest, search and seizure', [
        'General procedure for investigation',
        'Police power to require attendance and examine witnesses',
        'Statements to police and their use',
        'Recording confessions and statements before magistrate',
        'Arrest with and without warrant',
        'Necessity and proportionality of arrest',
        'Notice of appearance instead of arrest',
        'Rights of an arrested person',
        'Grounds of arrest and access to counsel',
        'Production before magistrate and remand',
        'Medical examination and safeguards',
        'Search warrants',
        'Search without warrant',
        'Seizure, inventory and chain of custody',
        'Audio-video recording and electronic procedure',
    ]),
    M('Bail', [
        'Purpose of bail and presumption of innocence',
        'Bail in bailable offences',
        'Bail in non-bailable offences',
        'Factors governing judicial discretion',
        'Anticipatory bail',
        'Conditions of bail',
        'Sureties, bonds and indigent accused',
        'Cancellation of bail',
        'Default or statutory bail',
        'Release of undertrial prisoners',
        'Bail under special statutes',
    ]),
    M('Pre-trial proceedings', [
        'Taking cognizance of offences',
        'Complaint examination and postponement of process',
        'Issue of process',
        'Supply of police papers',
        'Committal to the Court of Session',
        'Form and contents of charge',
        'Joinder and alteration of charges',
        'Discharge',
        'Framing of charge and standard of scrutiny',
    ]),
    M('Trial', [
        'Warrant trial on police report',
        'Warrant trial otherwise than on police report',
        'Summons trial',
        'Summary trial',
        'Plea of guilty',
        'Prosecution and defence evidence',
        'Production of witnesses by summons and warrant',
        'Examination of accused',
        'Trial in absentia and proclaimed offender concerns',
        'Withdrawal from prosecution',
        'Use of electronic mode in trial',
    ]),
    M('Rights of accused, victims and witnesses', [
        'Open court and public trial',
        'Independent and impartial tribunal',
        'Legal aid and effective representation',
        'Protection against ex post facto criminal law',
        'Protection against self-incrimination',
        'Protection against double jeopardy',
        'Right to be present and hear evidence',
        'Speedy trial',
        'Rights and participation of victims',
        'Victim compensation',
        'Witness protection scheme',
        'Vulnerable witness deposition centres',
        'In-camera proceedings and privacy',
    ]),
    M('Judgment and sentencing', [
        'Acquittal and discharge distinguished',
        'Conviction and findings on each charge',
        'Hearing on sentence',
        'Proportionality and aggravating or mitigating factors',
        'Contents and delivery of judgment',
        'Compensation and other consequential orders',
        'Death-sentence confirmation',
        'Correction and finality of judgment',
    ]),
    M('Alternative disposal of criminal cases', [
        'Plea bargaining: eligibility and exclusions',
        'Mutually satisfactory disposition',
        'Judgment and finality in plea bargaining',
        'Compounding of offences',
        'Compoundable offences with and without permission',
        'Withdrawal and quashing compared with compounding',
        'Probation of offenders',
        'Release after admonition or on good conduct',
    ]),
    M('Appeals and High Court powers', [
        'Right of appeal as statutory',
        'Appeal from conviction',
        'Appeal against acquittal',
        'Victim’s appeal',
        'Suspension of sentence pending appeal',
        'Revision',
        'Reference',
        'Inherent powers of the High Court',
        'Quashing criminal proceedings',
        'Finality, review limits and constitutional remedies',
    ]),
], edition='2025; BNSS 2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/LB-203%20Revised_.pdf',
   laws=['Bharatiya Nagarik Suraksha Sanhita, 2023', 'Constitution of India', 'Probation of Offenders Act, 1958'],
   prereq=['f09','f13','f14','f15','@lb-104.m10'], background=['@lb-201'], related=['@lb-201'], category='Criminal procedure'),

S('LB-204', 2, 'Property Law', [
    M('Movable and immovable property', [
        'Concept and legal incidents of property',
        'Movable and immovable property distinguished',
        'Land, benefits arising out of land and things attached to earth',
        'Fixtures and the degree-and-purpose tests',
        'Standing timber, growing crops and grass',
        'Actionable claims',
        'Transferability and public-policy limits',
    ]),
    M('Attestation', [
        'Purpose and legal importance of attestation',
        'Competence of attesting witnesses',
        'Animus attestandi',
        'Presence and acknowledgment requirements',
        'Mode of attestation',
        'Proof of attested documents',
        'Purdahnashin and vulnerable executants',
    ]),
    M('Notice', [
        'Actual notice',
        'Constructive notice',
        'Duty of inquiry',
        'Wilful abstention and gross negligence',
        'Notice from possession',
        'Notice from registration',
        'Notice to agent and imputation to principal',
        'Effect of notice on priority and good faith',
    ]),
    M('Meaning and mechanics of transfer', [
        'Transfer inter vivos',
        'Living persons and juristic persons',
        'Conveyance of present and future interests',
        'Partition distinguished from transfer',
        'Family arrangements',
        'Transfer by operation of law',
        'Competence to transfer',
        'Oral and written transfers',
    ]),
    M('What property may be transferred', [
        'General rule of transferability',
        'Spes successionis',
        'Mere right of re-entry',
        'Easements apart from dominant heritage',
        'Restricted interests and personal rights',
        'Public offices, salaries and pensions',
        'Transfers opposed to the nature of interest or law',
        'Feeding the grant by estoppel',
        'Transfer by unauthorized person who later acquires title',
    ]),
    M('Conditional transfers and obligations', [
        'Absolute and conditional interests',
        'Restraints on alienation',
        'Repugnant conditions',
        'Directions as to enjoyment',
        'Conditions precedent and subsequent',
        'Impossible, unlawful and immoral conditions',
        'Obligations annexed to ownership',
        'Notice and enforcement of restrictive obligations',
    ]),
    M('Unborn persons, perpetuity and accumulation', [
        'Transfer for benefit of an unborn person',
        'Prior interest and whole remaining interest',
        'Rule against perpetuity',
        'Vesting period and lives in being',
        'Transfer to a class and partial invalidity',
        'Accumulation of income',
        'Exceptions for public benefit',
        'Directions for maintenance and preservation',
    ]),
    M('Vested and contingent interests', [
        'Vested interest',
        'Postponed enjoyment',
        'Vesting on uncertain event',
        'Contingent interest',
        'Acceleration on failure of prior disposition',
        'Condition precedent versus condition subsequent',
        'Transfer to a class and age contingencies',
    ]),
    M('Lis pendens', [
        'Rationale of lis pendens',
        'Pending suit or proceeding',
        'Non-collusive litigation',
        'Direct and specific right in immovable property',
        'Commencement and conclusion of pendency',
        'Voluntary and involuntary alienations',
        'Effect on transferee pendente lite',
        'Court permission and equitable considerations',
    ]),
    M('Mortgages and charges', [
        'Mortgage, mortgagor, mortgagee and mortgage money',
        'Simple mortgage',
        'Mortgage by conditional sale',
        'Usufructuary mortgage',
        'English mortgage',
        'Mortgage by deposit of title deeds',
        'Anomalous mortgage',
        'Rights and liabilities of mortgagor and mortgagee',
        'Right of redemption',
        'Clog on redemption',
        'Foreclosure and sale',
        'Priority, subrogation and tacking',
        'Marshalling and contribution',
        'Charge distinguished from mortgage',
    ]),
    M('Lease and licence', [
        'Lease and its essential elements',
        'Duration and commencement',
        'Creation of leases',
        'Rights and liabilities of lessor and lessee',
        'Determination and forfeiture',
        'Holding over',
        'Waiver of forfeiture and notice to quit',
        'Licence and its essential elements',
        'Lease distinguished from licence',
        'Revocation and irrevocable licences',
    ]),
    M('Gifts', [
        'Gift and its essential elements',
        'Existing movable and immovable property',
        'Acceptance during donor’s lifetime',
        'Registration and delivery',
        'Onerous gifts',
        'Universal donee',
        'Suspension or revocation',
        'Gifts to several donees',
        'Gift distinguished from settlement and will',
    ]),
], edition='2022', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/IInd%20Term_Property%20Law_LB204%20_2022.pdf',
   laws=['Transfer of Property Act, 1882', 'Indian Easements Act, 1882', 'Registration Act, 1908'],
   prereq=['f10','f11','f15','@lb-102.m07'], related=['@lb-202','@lb-302'], category='Property law'),

S('LB-205', 2, 'Public International Law', [
    M('Nature and development of international law', [
        'Definition and claimed legal character of international law',
        'Development of international peace and security institutions',
        'United Nations and post-war legal order',
        'Generations of human rights',
        'Codification and the International Law Commission',
        'Sanctions and decentralized enforcement',
        'States as primary subjects',
        'International organizations as subjects',
        'Individuals and other participants',
        'International legal personality',
        'Third World Approaches to International Law',
        'Colonial history and distributional critique',
    ]),
    M('Sources of international law', [
        'Article 38 of the ICJ Statute',
        'Treaties and conventions',
        'Treaty formation, consent and pacta sunt servanda',
        'International custom: state practice',
        'Opinio juris',
        'Persistent objector and regional custom',
        'General principles of law',
        'Judicial decisions',
        'Teachings of publicists',
        'Ex aequo et bono',
        'General Assembly resolutions',
        'Security Council resolutions',
        'Advisory opinions',
        'Soft law and unilateral acts',
        'Hierarchy, jus cogens and obligations erga omnes',
    ]),
    M('International law and municipal law', [
        'Monist theory',
        'Dualist theory',
        'Incorporation and transformation',
        'Treaty-making power and domestic implementation',
        'Customary international law in domestic courts',
        'United Kingdom practice',
        'United States practice',
        'Indian constitutional practice',
        'Fundamental rights and international norms',
        'Using treaties as interpretive aids',
    ]),
    M('State responsibility', [
        'Basis of international responsibility',
        'Internationally wrongful act',
        'Breach of an international obligation',
        'Damage theory',
        'Fault theory',
        'Absolute liability and risk theory',
        'Attribution of state organs',
        'Ultra vires conduct and non-state actors',
        'Circumstances precluding wrongfulness',
        'Cessation and non-repetition',
        'Restitution',
        'Compensation or indemnity',
        'Satisfaction',
        'Exhaustion of local remedies',
        'Diplomatic protection',
        'ILC Articles on State Responsibility',
    ]),
    M('Law of the sea', [
        'Baselines and internal waters',
        'Territorial sea',
        'Innocent passage',
        'Straits and archipelagic waters',
        'Contiguous zone',
        'Exclusive economic zone',
        'Continental shelf',
        'High seas freedoms',
        'Nationality and jurisdiction over ships',
        'Maritime boundary delimitation',
        'Opposite and adjacent coasts',
        'International seabed Area',
        'Common heritage of mankind',
        'Marine environmental duties',
        'UNCLOS dispute settlement',
    ]),
    M('State jurisdiction', [
        'Territorial principle',
        'Nationality principle',
        'Passive-personality principle',
        'Protective principle',
        'Universal jurisdiction',
        'Effects doctrine and extraterritoriality',
        'Concurrent jurisdiction',
        'Enforcement jurisdiction limits',
        'Extradition',
        'Double criminality and political-offence exception',
        'Asylum',
        'State immunity',
    ]),
    M('Diplomatic and consular relations', [
        'Rationale for diplomatic privileges and immunities',
        'Diplomatic premises and archives',
        'Personal inviolability',
        'Immunity from criminal and civil jurisdiction',
        'Waiver and persona non grata',
        'Duties of diplomats',
        'Consular functions',
        'Consular premises and communications',
        'Consular notification and access',
        'Diplomatic protection distinguished from immunity',
    ]),
], edition='2022', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/IInd%20Term_Public%20InternationalLaw_LB205_2022%20.pdf',
   laws=['Charter of the United Nations, 1945', 'Statute of the International Court of Justice', 'Vienna Convention on Diplomatic Relations, 1961', 'Vienna Convention on Consular Relations, 1963', 'United Nations Convention on the Law of the Sea, 1982'],
   prereq=['f05','f09','f10','f11','f16','@lb-106.m03'], related=['@lb-301'], category='International law'),
]

# Term III --------------------------------------------------------------------
SUBJECTS += [
S('LB-301', 3, 'Constitutional Law I', [
    M('Constitutional foundations', [
        'Making of the Constitution of India',
        'Constituent Assembly and constitutional choices',
        'Aims, values and the Preamble',
        'Salient features of the Constitution',
        'Parliamentary government',
        'Federalism with unitary features',
        'Constitutional supremacy',
        'Separation of powers',
        'Rule of law',
        'Basic structure doctrine: introduction',
        'Scheduled and tribal areas',
        'Asymmetrical federal arrangements',
    ]),
    M('The Union and its territory', [
        'India as a Union of States',
        'Territory of India',
        'Admission and establishment of new States',
        'Formation of new States',
        'Alteration of area, boundaries and names',
        'Parliamentary procedure under Articles 2–4',
        'Cession and acquisition of territory',
        'State consent and federal implications',
        'Special territorial arrangements',
    ]),
    M('Union and State executives', [
        'President: election, qualifications and term',
        'Executive power of the Union',
        'Aid and advice of the Council of Ministers',
        'Prime Minister and collective responsibility',
        'President’s discretionary and reserve powers',
        'Pardoning power',
        'Immunities of President and Governors',
        'Governor: appointment, tenure and removal',
        'State Council of Ministers and Chief Minister',
        'Governor’s discretion and constitutional limits',
        'Delhi and special federal executive arrangements',
    ]),
    M('Parliament and State legislatures', [
        'Composition of Parliament',
        'Rajya Sabha and Lok Sabha',
        'Composition of State legislatures',
        'Qualifications and disqualifications of members',
        'Office of profit',
        'Anti-defection framework: introduction',
        'Sessions, prorogation and dissolution',
        'Presiding officers',
        'Legislative procedure',
        'Ordinary Bills',
        'Money Bills and Finance Bills',
        'Legislative privileges',
        'Judicial review of legislative proceedings',
        'Free speech inside the House',
    ]),
    M('Legislative power of the executive: ordinances', [
        'Constitutional basis of ordinance power',
        'Conditions for promulgation',
        'Satisfaction of President or Governor',
        'Duration and legislative replacement',
        'Re-promulgation and constitutional fraud',
        'Judicial review of ordinances',
        'Rights and liabilities created by lapsed ordinances',
    ]),
    M('Union and State judiciary', [
        'Supreme Court composition',
        'High Court composition',
        'Appointment and qualifications of judges',
        'Collegium system and judicial appointments',
        'NJAC and judicial independence',
        'Transfer and removal of judges',
        'Original jurisdiction',
        'Appellate jurisdiction',
        'Special leave jurisdiction',
        'Advisory jurisdiction',
        'Review and curative jurisdiction',
        'Court of record and contempt power',
        'High Court writ and supervisory jurisdiction',
        'Tribunal review and L. Chandra Kumar',
        'Procedural requirements for constitutional litigation',
        'Public interest litigation',
        'Epistolary jurisdiction and continuing mandamus',
        'Open justice, review in death cases and institutional accountability',
    ]),
    M('Distribution of legislative powers', [
        'Union, State and Concurrent Lists',
        'Residuary power',
        'Territorial nexus',
        'Extra-territorial legislation',
        'Pith and substance',
        'Incidental and ancillary powers',
        'Colourable legislation',
        'Harmonious construction of entries',
        'Occupied field',
        'Repugnancy under Article 254',
        'Presidential assent and State law',
        'Parliamentary power in national interest or emergency',
        'Legislation by consent of States',
        'Treaty-implementation power',
        'Delegation of legislative power',
        'Federal taxation and competence',
    ]),
    M('Freedom of trade, commerce and intercourse', [
        'Article 301 and economic unity',
        'Direct and immediate restrictions',
        'Regulatory and compensatory measures',
        'Parliamentary restrictions in public interest',
        'State taxation and non-discrimination',
        'Presidential sanction requirements',
        'Government monopoly and trade freedom',
        'GST-era federal commerce questions',
    ]),
    M('Emergency provisions', [
        'National emergency: grounds and proclamation',
        'Parliamentary approval and duration',
        'Effects on executive and legislative relations',
        'Articles 358 and 359',
        'State emergency or President’s Rule',
        'Material and judicial review under S. R. Bommai',
        'Legislative and executive consequences of Article 356',
        'Financial emergency',
        'Emergency power and constitutional safeguards',
        'The 44th Amendment reforms',
    ]),
], edition='2022', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/LB-301-Constitutional%20Law-I%20_2022.pdf',
   laws=['Constitution of India'], prereq=['@lb-106.m07','@lb-205.m03','f16'], category='Constitutional law'),

S('LB-302', 3, 'Code of Civil Procedure and Limitation Act', [
    M('CPC concepts and decrees', [
        'Object and scheme of the Code of Civil Procedure, 1908',
        'Suit of a civil nature',
        'Decree, judgment and order',
        'Preliminary, final and partly preliminary decrees',
        'Mesne profits',
        'Legal representative',
        'Foreign court and foreign judgment',
        'Execution and decree-holder or judgment-debtor',
    ]),
    M('Jurisdiction, res sub judice and res judicata', [
        'Subject-matter, territorial and pecuniary jurisdiction',
        'Exclusion of civil-court jurisdiction',
        'Objection to jurisdiction and waiver',
        'Res sub judice',
        'Res judicata',
        'Constructive res judicata',
        'Issue estoppel and cause-of-action estoppel',
        'Res judicata in public law and execution',
        'Foreign judgments and conclusiveness',
    ]),
    M('Place of suing and transfer', [
        'Suits concerning immovable property',
        'Suits for compensation for wrongs',
        'Residence, business and cause of action',
        'Objections to place of suing',
        'Transfer and withdrawal of suits',
        'Forum conveniens concerns',
    ]),
    M('Execution and garnishee proceedings', [
        'Court executing a decree',
        'Transfer of decrees for execution',
        'Modes of execution',
        'Attachment and sale',
        'Arrest and detention in execution',
        'Questions to be determined by executing court',
        'Resistance and obstruction',
        'Garnishee orders',
        'Rateable distribution',
        'Stay of execution',
    ]),
    M('Suits by or against government and public officers', [
        'Statutory notice before suit',
        'Parties and form of government suits',
        'Urgent relief without notice',
        'Execution against government',
        'Public officers and official acts',
        'Sovereign-immunity and public-law overlap',
    ]),
    M('Appeals', [
        'First appeal from original decree',
        'Powers of appellate court',
        'Additional evidence on appeal',
        'Cross-objections',
        'Second appeal and substantial question of law',
        'Appeals from orders',
        'Appeals by indigent persons',
        'Effect of appeal and stay',
    ]),
    M('Reference, review and revision', [
        'Reference to High Court',
        'Review: grounds and limits',
        'Revision: jurisdictional error',
        'Revision distinguished from appeal',
        'Review distinguished from recall and appeal',
        'Supervisory jurisdiction and CPC remedies',
    ]),
    M('Inherent powers', [
        'Section 151 and preservation of justice',
        'Abuse of process',
        'Recall of orders obtained by fraud',
        'Restitution',
        'Transfer and consolidation',
        'Limits where express provisions govern',
    ]),
    M('Parties to suits', [
        'Necessary and proper parties',
        'Joinder of plaintiffs and defendants',
        'Misjoinder and non-joinder',
        'Representative suits',
        'Addition, deletion and substitution of parties',
        'Death, marriage and insolvency of parties',
        'Intervention and third-party interests',
    ]),
    M('Pleadings and amendment', [
        'Material facts versus evidence',
        'Particulars and verification',
        'Alternative and inconsistent pleadings',
        'Admissions and denials',
        'Amendment before and after commencement of trial',
        'Due-diligence proviso',
        'Relation back and limitation',
        'Withdrawal of admissions',
    ]),
    M('Plaint and rejection', [
        'Contents and institution of plaint',
        'Cause of action and valuation',
        'Return of plaint',
        'Rejection for no cause of action',
        'Undervaluation and insufficient stamp',
        'Suit barred by law',
        'Reading plaint as a whole',
        'Effect of rejection and fresh plaint',
    ]),
    M('Appearance and non-appearance', [
        'Service of summons',
        'Appearance in person or through pleader',
        'Ex parte proceedings',
        'Dismissal for default',
        'Restoration of suit',
        'Setting aside ex parte decree',
        'Sufficient cause',
        'Consequences of non-appearance at different stages',
    ]),
    M('Summary suits', [
        'Scope of Order XXXVII',
        'Eligible instruments and claims',
        'Entry of appearance',
        'Summons for judgment',
        'Leave to defend',
        'Substantial defence and triable issue',
        'Conditional leave',
        'Decree and setting aside',
    ]),
    M('Temporary injunctions and interlocutory orders', [
        'Prima facie case',
        'Balance of convenience',
        'Irreparable injury',
        'Status quo and mandatory interim injunction',
        'Ex parte injunction and disclosure duties',
        'Attachment before judgment',
        'Appointment of receiver',
        'Security for costs',
        'Commissions',
        'Breach and enforcement of interim orders',
    ]),
    M('Special and miscellaneous CPC procedures', [
        'Court-referred alternative dispute resolution',
        'Precepts',
        'Interpleader suits',
        'Suits by indigent persons',
        'Caveat',
        'Compromise of suits',
        'Withdrawal and abandonment',
        'Judgment on admissions',
        'Costs and realistic costs',
        'Electronic filing and case management',
    ]),
    M('Limitation: institution and extension', [
        'Purpose and policy of limitation law',
        'Bar of limitation under section 3',
        'Court duty to apply limitation',
        'Limitation distinguished from laches',
        'Extension for appeals and applications',
        'Sufficient cause under section 5',
        'Exclusion for wrong forum and good faith',
        'Legal disability',
    ]),
    M('Computation of limitation', [
        'Exclusion of first and last day',
        'Time obtaining copies',
        'Fraud and mistake',
        'Acknowledgment in writing',
        'Part-payment',
        'Continuing breach and continuing tort',
        'Adding or substituting parties',
        'Effect of death and legal disability',
    ]),
    M('Adverse possession and extinguishment', [
        'Limitation for suits to recover possession',
        'Possession that is actual, open and hostile',
        'Animus possidendi',
        'Permissive possession',
        'Co-owners and adverse possession',
        'Government land and longer periods',
        'Extinguishment of title under section 27',
        'Constitutional and policy critiques',
    ]),
    M('The Limitation Act schedule', [
        'Articles for suits',
        'Articles for appeals',
        'Articles for applications',
        'Starting point of limitation',
        'Residual articles',
        'Recurring causes and instalments',
        'Choosing the correct article',
    ]),
], edition='2025', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/LB-302-CPC%20%26%20Limitation%20_%202025.pdf',
   laws=['Code of Civil Procedure, 1908', 'Limitation Act, 1963', 'Commercial Courts Act, 2015'],
   prereq=['f09','f14','f15','@lb-201.m03','@lb-204.m09'], related=['@lb-502','@lb-602'], category='Civil procedure'),

S('LB-303', 3, 'Company Law', [
    M('Nature and kinds of companies', [
        'Evolution and purposes of company law',
        'Definition and essential features of company',
        'Incorporated association and perpetual succession',
        'Separate legal personality',
        'Limited liability',
        'Company distinguished from partnership',
        'Company distinguished from LLP',
        'One person, private and public companies',
        'Section 8 companies',
        'Holding, subsidiary and associate companies',
        'Government and foreign companies',
        'Lifting or piercing the corporate veil',
        'Statutory, judicial and fraud-based veil piercing',
    ]),
    M('Promotion and formation', [
        'Promoter and pre-incorporation activity',
        'Fiduciary duties of promoters',
        'Disclosure of profit and conflict',
        'Pre-incorporation contracts',
        'Incorporation documents and process',
        'Certificate of incorporation',
        'Conclusive effect and fraud in incorporation',
        'Registered office, name and commencement',
    ]),
    M('Constitutional documents', [
        'Memorandum of association',
        'Objects, liability, capital and subscription clauses',
        'Alteration of memorandum',
        'Doctrine of ultra vires',
        'Articles of association',
        'Alteration of articles',
        'Entrenchment and shareholder agreements',
        'Binding effect of memorandum and articles',
        'Constructive notice',
        'Indoor-management rule',
        'Exceptions to indoor management',
        'Actual and apparent authority',
    ]),
    M('Capital-market instruments', [
        'Prospectus and public offer',
        'Shelf, red-herring and deemed prospectus',
        'Contents and material disclosure',
        'Civil and criminal liability for misstatement',
        'Private placement and rights issue',
        'Shares and share capital',
        'Equity and preference shares',
        'Allotment and calls',
        'Transfer and transmission of securities',
        'Buy-back and reduction of capital',
        'Debentures and charges',
        'Depository and dematerialized securities',
    ]),
    M('Board of directors', [
        'Corporate management and board structure',
        'Appointment and qualifications of directors',
        'Director identification number',
        'Independent and woman directors',
        'Disqualification, vacation and removal',
        'Powers of Board and reserved shareholder matters',
        'Fiduciary and statutory duties',
        'Duty of care, skill and diligence',
        'Conflict of interest and related-party transactions',
        'Loans to directors and corporate opportunities',
        'Board meetings and committees',
        'Director liability and business-judgment concerns',
        'Satyam and corporate-governance failure',
    ]),
    M('General meetings', [
        'Annual and extraordinary general meetings',
        'Notice, agenda and explanatory statement',
        'Quorum and chairing',
        'Ordinary and special resolutions',
        'Voting, proxies and postal ballot',
        'Minutes and records',
        'Requisitioned meetings',
        'Class meetings',
        'Minority participation and electronic meetings',
    ]),
    M('Oppression and mismanagement', [
        'Majority rule and Foss v Harbottle',
        'Exceptions to majority rule',
        'Derivative action',
        'Oppressive conduct',
        'Mismanagement and public-interest prejudice',
        'Eligibility and waiver',
        'Tribunal powers and preventive orders',
        'Just-and-equitable considerations',
        'Corporate deadlock and quasi-partnership',
        'Class action under company law',
    ]),
    M('Winding up and insolvency interface', [
        'Meaning and effects of winding up',
        'Tribunal winding up grounds',
        'Inability to pay debts and IBC displacement',
        'Just and equitable ground',
        'Petition, admission and provisional liquidator',
        'Powers and duties of liquidator',
        'Contributories and distribution',
        'Fraudulent conduct and misfeasance',
        'Voluntary liquidation under insolvency law',
        'Dissolution and restoration',
    ]),
    M('Adjudicatory and regulatory bodies', [
        'Registrar of Companies',
        'Central Government and Regional Directors',
        'Serious Fraud Investigation Office',
        'National Company Law Tribunal',
        'National Company Law Appellate Tribunal',
        'Special courts',
        'SEBI and listed companies',
        'Jurisdictional overlap with civil courts and IBC forums',
    ]),
    M('Contemporary company-law developments', [
        'Corporate social responsibility',
        'Beneficial ownership and shell-company concerns',
        'Class actions and investor remedies',
        'Corporate criminal liability',
        'Environmental, social and governance reporting',
        'Data, technology and virtual governance',
        'Startup financing and convertible instruments',
        'Stakeholder governance versus shareholder primacy',
    ]),
], edition='2025', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/LB-303-Company%20Law%20_2025%20Final_.pdf',
   laws=['Companies Act, 2013', 'Securities and Exchange Board of India Act, 1992', 'Insolvency and Bankruptcy Code, 2016', 'Limited Liability Partnership Act, 2008'],
   prereq=['f10','f11','f15','@lb-102.m07','@lb-204.m04'], related=['@lb-5036','@lb-4033'], category='Corporate law'),

S('LB-304', 3, 'Special Contracts', [
    M('Agency and partnership foundations', [
        'Creation of agency by express and implied authority',
        'Agency by necessity, estoppel and holding out',
        'Ratification',
        'Scope of actual and apparent authority',
        'Sub-agents and substituted agents',
        'Duties and rights of agent and principal',
        'Personal liability of agent',
        'Termination and irrevocable agency',
        'Definition of partnership and firm',
        'Real relation test and sharing profits',
        'Partnership at will and particular partnership',
        'Partnership distinguished from company, co-ownership and LLP',
    ]),
    M('Relations of partners', [
        'General duties of partners',
        'Duty of good faith and disclosure',
        'Indemnity for fraud and wilful neglect',
        'Rights and duties by contract',
        'Participation in business and access to books',
        'Remuneration and interest',
        'Firm property and goodwill',
        'Sharing profits and losses',
        'Partner as agent of firm',
        'Implied authority',
        'Emergency authority',
        'Holding out',
        'Liability for acts, wrongs and misapplication',
    ]),
    M('Incoming and outgoing partners; registration', [
        'Admission of a new partner',
        'Liability of incoming partner',
        'Retirement',
        'Expulsion',
        'Insolvency and death',
        'Continuing liability and public notice',
        'Rights of outgoing partner',
        'Registration of firms',
        'Effect of non-registration',
        'Suits by firms and partners',
    ]),
    M('Dissolution of partnership', [
        'Dissolution of firm and partnership distinguished',
        'Dissolution by agreement',
        'Compulsory dissolution',
        'Dissolution on contingencies',
        'Dissolution by notice',
        'Dissolution by court',
        'Authority and liability after dissolution',
        'Settlement of accounts',
        'Payment of debts and partner advances',
        'Goodwill and restraint of trade',
    ]),
    M('Formation of contract of sale', [
        'Sale and agreement to sell',
        'Goods: existing, future and contingent',
        'Price and methods of fixing it',
        'Formalities and implied terms',
        'Perishing goods before or after agreement',
        'Sale distinguished from hire-purchase, barter and works contract',
    ]),
    M('Conditions and warranties', [
        'Condition and warranty distinguished',
        'When condition is treated as warranty',
        'Implied condition as to title',
        'Sale by description',
        'Sale by sample',
        'Fitness for purpose',
        'Merchantable or satisfactory quality',
        'Caveat emptor and exceptions',
        'Express terms and exclusion clauses',
    ]),
    M('Transfer of property, title and risk', [
        'Intention of parties and passing of property',
        'Specific and unascertained goods',
        'Appropriation',
        'Goods sent on approval or sale or return',
        'Reservation of right of disposal',
        'Risk prima facie passes with property',
        'Transfer of title by non-owner',
        'Nemo dat rule',
        'Estoppel, mercantile agent and joint-owner exceptions',
        'Voidable title and seller or buyer in possession',
        'Delivery and acceptance',
    ]),
    M('Unpaid seller', [
        'Who is an unpaid seller',
        'Lien',
        'Stoppage in transit',
        'Resale',
        'Withholding delivery',
        'Rights against buyer personally',
        'Suit for price',
        'Damages for non-acceptance',
        'Effect of sub-sale or pledge by buyer',
    ]),
], edition='2020 archive', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/304%20Special%20Contracts%20July%202020%20%2818%20files%20merged%29%20%2814%20files%20merged%29%20%288%20files%20merged%29%20%281%29.pdf', source_status='official archive',
   laws=['Indian Contract Act, 1872', 'Indian Partnership Act, 1932', 'Sale of Goods Act, 1930', 'Limited Liability Partnership Act, 2008'],
   prereq=['@lb-102.m11'], elective=True, category='Commercial law'),

S('LB-3031', 3, 'Media and Law', [
    M('Media forms, history and legal setting', [
        'Print media',
        'Broadcast media',
        'Cinema and audiovisual media',
        'Digital and social media',
        'Historical development of press law in India',
        'Colonial controls and post-Constitution change',
        'Legislative and policy efforts concerning media',
        'Media ownership, concentration and pluralism',
    ]),
    M('Media freedom, speech and information', [
        'Article 19(1)(a) and freedom of the press',
        'Reasonable restrictions under Article 19(2)',
        'Right to know and receive information',
        'Right to broadcast and spectrum regulation',
        'Hate speech and incitement',
        'Privacy of ordinary persons',
        'Public figures and reasonable expectation of privacy',
        'Paparazzi and intrusive newsgathering',
        'Illegally obtained information',
        'Right of publicity',
        'Right to be forgotten',
        'Defamation of public persons',
        'Falsity, actual harm and right of reply',
        'Sting operations and investigative journalism',
        'Leveson inquiry and comparative lessons',
        'Access to information under RTI law',
        'Access to meetings and public records',
        'Protection and disclosure of journalistic sources',
        'Media trial and presumption of innocence',
        'Pre-trial publicity and fair trial',
        'Cameras in court and live streaming',
        'Postponement and restrictive reporting orders',
    ]),
    M('Contempt and reporting courts', [
        'Civil and criminal contempt in media reporting',
        'Scandalising the court',
        'Vilification of judges',
        'Fair and accurate reports',
        'Fair criticism of judicial acts',
        'Unverified allegations and sub judice reporting',
        'Contempt, free speech and institutional accountability',
    ]),
    M('Regulation and self-regulation', [
        'Press Council and print-media standards',
        'Registration and regulation of newspapers',
        'Public-service broadcasting',
        'Private broadcast licensing and programme codes',
        'News Broadcasting standards and self-regulation',
        'Film certification institutions',
        'Digital news and intermediary regulation',
        'Social-media platform governance',
        'Safe harbours and notice systems',
        'Independence, capture and accountability of regulators',
    ]),
    M('Advertising', [
        'Commercial speech',
        'Misleading and unfair advertisements',
        'Surrogate and prohibited advertising',
        'Comparative advertising and disparagement',
        'Government advertising and public funds',
        'Political advertising and election silence',
        'Influencers, endorsements and disclosure',
        'Children and vulnerable consumers',
    ]),
    M('Censorship and gag orders', [
        'Prior restraint and post-publication liability',
        'Film censorship and certification',
        'Obscenity standards',
        'Community standards and artistic merit',
        'Variable obscenity and child protection',
        'Gag orders across print, broadcast and digital media',
        'Judicial reporting restrictions',
        'Protection of sexual-offence victims and juveniles',
        'Blocking and takedown of online content',
    ]),
    M('Legislative proceedings and media', [
        'Parliamentary privilege',
        'Publication of legislative proceedings',
        'Expunged portions and secret sittings',
        'Fair and accurate reporting protection',
        'Broadcasting legislative proceedings',
        'Privilege, contempt and judicial review',
    ]),
], edition='2022', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/LB-3031%E2%80%93%20Media%20Law%20And%20Censorship%20%28INCL.%20SELF%20REGULATION%29I%202022.pd.pdf',
   laws=['Constitution of India', 'Right to Information Act, 2005', 'Contempt of Courts Act, 1971', 'Information Technology Act, 2000', 'Cinematograph Act, 1952', 'Consumer Protection Act, 2019'],
   prereq=['@lb-301.m04','@lb-103.m08','@lb-201.m05'], elective=True, category='Media and technology law'),

S('LB-3032', 3, 'Private International Law', [
    M('Nature, scope and method of conflict of laws', [
        'Definition and scope of private international law',
        'Foreign element',
        'Difference from public international law',
        'Unification and Hague conventions',
        'Blurring of public and private international law',
        'India’s federal and personal-law conflicts',
        'Commercial transactions and cyberspace',
        'Lex fori and forum rules',
        'Jurisdiction over immovable property',
        'Admiralty in rem jurisdiction',
        'Carriage by air jurisdiction',
        'Matrimonial and child-custody jurisdiction',
        'In personam jurisdiction under CPC',
        'Anti-suit injunctions',
        'Choice of law',
        'Characterization',
        'Renvoi',
        'Proof, application and exclusion of foreign law',
        'Public policy and mandatory rules',
    ]),
    M('Domicile', [
        'Meaning and functions of domicile',
        'Domicile in the Indian context',
        'Primary and secondary domicile',
        'Domicile of origin',
        'Domicile of choice',
        'Residence and intention to remain',
        'Domicile of dependants',
        'Domicile of fugitives',
        'Domicile of corporations',
        'Domicile distinguished from nationality and residence',
    ]),
    M('Proper law of contract', [
        'Evolution of the proper-law theory',
        'Express choice of law',
        'Implied choice of law',
        'Closest and most real connection',
        'Limits of party autonomy',
        'Mandatory rules and public policy',
        'English common-law position',
        'Rome Convention and Rome I approach',
        'Indian position',
        'Arbitration clauses and governing law',
        'International commercial contracts',
    ]),
    M('Choice of law in tort', [
        'Lex fori',
        'Lex loci delicti',
        'Double-actionability rule',
        'Proper law or social-environment theory',
        'Flexible exception',
        'English statutory reform',
        'Rome II framework',
        'Indian cases and policy',
        'Cross-border internet torts',
        'Multiple places of conduct and harm',
    ]),
    M('Marriage, matrimonial relief, adoption and custody', [
        'Capacity to marry',
        'Formal validity of marriage',
        'Essential validity and personal law',
        'Recognition of foreign marriages',
        'Jurisdiction in matrimonial proceedings',
        'Choice of law in divorce',
        'Recognition of foreign divorce',
        'Fraud, notice and natural justice',
        'Inter-country adoption',
        'Child custody and ordinary residence',
        'Best interests of the child',
        'Comity and return of children',
    ]),
    M('Foreign judgments', [
        'Recognition distinguished from enforcement',
        'Conclusive foreign judgments under section 13 CPC',
        'Competent jurisdiction',
        'Decision on merits',
        'Natural justice',
        'Fraud',
        'Refusal where founded on incorrect international or Indian law',
        'Breach of Indian law',
        'Reciprocating territories and section 44A CPC',
        'Execution and fresh suits',
        'Foreign matrimonial judgments',
    ]),
    M('Foreign arbitral awards', [
        'Recognition and enforcement of foreign awards',
        'New York Convention framework',
        'Seat and nationality of award',
        'Limited refusal grounds',
        'Validity of arbitration agreement',
        'Notice and opportunity to present case',
        'Excess of jurisdiction',
        'Setting aside at the seat',
        'Arbitrability and public policy',
        'Enforcement in India',
    ]),
], edition='2020 archive', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/LB-3032-Private%20International%20Law%20%281%29.pdf', source_status='official archive',
   laws=['Code of Civil Procedure, 1908', 'Arbitration and Conciliation Act, 1996', 'Guardians and Wards Act, 1890', 'Carriage by Air Act, 1972'],
   prereq=['@lb-205.m03','@lb-204.m09','@lb-102.m11','@lb-105.m09'], elective=True, category='International and conflict law'),

S('LB-3037', 3, 'White Collar Crimes', [
    M('Concept and range of white-collar crime', [
        'Meaning and characteristics of white-collar crime',
        'White-collar crime distinguished from conventional crime',
        'Occupational and corporate crime',
        'Economic, financial and regulatory offences',
        'Victims, diffuse harm and under-reporting',
        'Corporate criminal liability',
        'Mens rea in organizational offending',
        'Enforcement agencies and overlapping statutes',
        'Sanctions, confiscation and compliance',
    ]),
    M('Criminological explanations', [
        'Sutherland’s conception of white-collar crime',
        'Differential association',
        'Opportunity and organizational culture',
        'Fraud triangle: pressure, opportunity and rationalization',
        'Techniques of neutralization',
        'Regulatory capture and elite power',
        'Deterrence, compliance and responsive regulation',
    ]),
    M('Food safety offences', [
        'Objects and structure of the Food Safety and Standards Act, 2006',
        'Food, unsafe food, sub-standard and misbranded food',
        'Food Safety and Standards Authority of India',
        'Commissioner and designated officers',
        'Food safety officers and analysts',
        'General principles of food safety',
        'Licensing and registration',
        'Purchaser sampling and analysis',
        'Improvement and prohibition notices',
        'Offences, penalties and adjudication',
        'Company liability and defences',
    ]),
    M('Narcotic drugs and psychotropic substances', [
        'Objects and policy of the NDPS Act',
        'Narcotic drug, psychotropic substance and controlled substance',
        'Authorities and the National Fund',
        'Prohibition and regulated medical or scientific use',
        'Possession, cultivation, manufacture and trafficking offences',
        'Small, intermediate and commercial quantity',
        'Financing illicit traffic and harbouring offenders',
        'Presumptions of culpable mental state and possession',
        'Search, seizure and arrest safeguards',
        'Sampling, inventory and chain of custody',
        'Bail restrictions',
        'Confiscation and forfeiture',
    ]),
    M('Corruption offences', [
        'Need for anti-corruption law',
        'Central and State investigative agencies',
        'Public servant and undue advantage',
        'Bribery by public servant',
        'Bribe giving and commercial organization liability',
        'Influence peddling and personal influence',
        'Criminal misconduct',
        'Attempt and abetment',
        'Investigation authorization',
        'Prior approval under section 17A',
        'Sanction for prosecution',
        'Statutory presumptions',
        'Attachment, trial and sentencing',
    ]),
    M('Money laundering', [
        'Magnitude, stages and methods of money laundering',
        'Placement, layering and integration',
        'Proceeds of crime and scheduled offence',
        'Money-laundering offence and continuing activity',
        'Knowledge, possession, concealment, use and projection as untainted',
        'Punishment and burden provisions',
        'Enforcement Directorate powers',
        'Provisional attachment',
        'Survey, search, seizure and freezing',
        'Arrest and safeguards',
        'Adjudication and confirmation',
        'Special courts and trial',
        'Vesting and confiscation',
        'Reporting-entity obligations and beneficial ownership',
        'International cooperation and reciprocal arrangements',
    ]),
], edition='2026', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/LB%203037%20Case%20Material%202026_compressed.pdf',
   laws=['Food Safety and Standards Act, 2006', 'Narcotic Drugs and Psychotropic Substances Act, 1985', 'Prevention of Corruption Act, 1988', 'Prevention of Money Laundering Act, 2002'],
   prereq=['@lb-104.m10','@lb-203.m03','@lb-303.m05'], elective=True, category='Criminal and regulatory law'),
]

# Term IV ---------------------------------------------------------------------
SUBJECTS += [
S('LB-401', 4, 'Constitutional Law II', [
    M('State action and laws inconsistent with fundamental rights', [
        'Meaning of State under Article 12',
        'Government departments and legislatures',
        'Local and other authorities',
        'Instrumentality or agency tests',
        'Private bodies performing public functions',
        'Judiciary as State',
        'Meaning of law under Article 13',
        'Pre-Constitution and post-Constitution laws',
        'Doctrine of eclipse',
        'Doctrine of severability',
        'Waiver of fundamental rights',
        'Personal laws and Article 13',
        'Judicial review as constitutional structure',
    ]),
    M('Equality', [
        'Equality before law and equal protection',
        'Reasonable classification',
        'Intelligible differentia and rational nexus',
        'Single-person and under-inclusive classifications',
        'Special courts and procedural classifications',
        'Arbitrariness as an equality violation',
        'Manifest arbitrariness',
        'State largesse and non-arbitrary allocation',
        'Substantive equality',
        'Protective discrimination',
        'Reservations for socially and educationally backward classes',
        'Scheduled Castes and Scheduled Tribes',
        'Reservations in public employment',
        'Creamy layer',
        'Promotion, consequential seniority and adequacy of representation',
        'Economically weaker sections',
        'Gender, disability, sexuality and intersectional equality',
    ]),
    M('Freedoms and personal liberty', [
        'Citizenship requirement for Article 19',
        'Corporate and associational claims',
        'Freedom of speech and expression',
        'Press, commercial speech and right to know',
        'Assembly and association',
        'Movement and residence',
        'Profession, occupation, trade and business',
        'Reasonable restrictions and proportionality',
        'Ex post facto criminal laws',
        'Double jeopardy',
        'Self-incrimination',
        'Life and personal liberty',
        'Procedure established by law and due process',
        'Dignity, privacy and autonomy',
        'Livelihood, health, shelter, education and environment',
        'Fair, just and reasonable procedure',
        'Rights on arrest and detention',
        'Preventive detention',
        'Communication of grounds and advisory boards',
    ]),
    M('Protection against exploitation', [
        'Traffic in human beings',
        'Begar and forced labour',
        'Minimum wages and forced labour',
        'Child labour in hazardous employment',
        'Bonded labour and rehabilitation',
        'Horizontal application and state duty to protect',
    ]),
    M('Freedom of religion', [
        'Freedom of conscience',
        'Profession, practice and propagation',
        'Essential religious practices',
        'Public order, morality and health',
        'Secular activities associated with religion',
        'Religious denominations',
        'Management of religious affairs',
        'Taxes for promotion of religion',
        'Religious instruction in educational institutions',
        'Secularism and constitutional morality',
    ]),
    M('Cultural and educational rights', [
        'Protection of language, script and culture',
        'Minority identity',
        'Right to establish educational institutions',
        'Right to administer and regulatory limits',
        'Aid and non-discrimination',
        'Admissions, standards and professional education',
        'Minority status and institutional character',
    ]),
    M('Constitutional remedies', [
        'Judicial review as basic structure',
        'Article 32 and Article 226 compared',
        'Habeas corpus',
        'Mandamus',
        'Certiorari',
        'Prohibition',
        'Quo warranto',
        'Locus standi',
        'Public interest litigation',
        'Res judicata and constructive res judicata',
        'Delay, laches and acquiescence',
        'Alternative remedy',
        'Territorial jurisdiction',
        'Compensation in writ jurisdiction',
        'Continuing mandamus and structural remedies',
    ]),
    M('Fundamental duties', [
        'Text and purpose of Article 51A',
        'Justiciability and indirect enforcement',
        'Duties as interpretive aids',
        'Environment, scientific temper and public property',
        'Harmony, dignity of women and constitutional citizenship',
        'Critiques of duty discourse',
    ]),
    M('Directive Principles of State Policy', [
        'Nature and non-justiciability',
        'Socialist, Gandhian and liberal-intellectual principles',
        'Welfare state and distributive justice',
        'Uniform civil code',
        'Legal aid and equal justice',
        'Public health, labour and environment',
        'Fundamental rights–DPSP relationship',
        'Harmony, conflict and basic structure',
        'Using DPSPs in interpretation and remedies',
    ]),
    M('Civil services', [
        'Doctrine of pleasure',
        'Constitutional protections in dismissal, removal or reduction in rank',
        'Opportunity of hearing and exceptions',
        'Public Service Commissions',
        'Recruitment rules and equality',
        'Service tribunals and judicial review',
        'Temporary, probationary and contractual public employment',
    ]),
    M('Amendment and basic structure', [
        'Amending power under Article 368',
        'Procedure and special majorities',
        'Ratification by States',
        'Early fundamental-rights amendment cases',
        'Kesavananda Bharati',
        'Elements of basic structure',
        'Limited amending power',
        'Judicial review of amendments',
        'Ninth Schedule review',
        'Constitutional identity and transformative change',
    ]),
], edition='2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/IVth%20Term_Constitution%20Law_LB%20401_2023.pdf',
   laws=['Constitution of India'], prereq=['@lb-301.m09'], related=['@lb-402','@lb-4031'], category='Constitutional law'),

S('LB-402', 4, 'Administrative Law', [
    M('Nature, scope and constitutional setting', [
        'Meaning and growth of administrative law',
        'Administrative state and welfare functions',
        'Rule of law',
        'Separation of powers',
        'Classification of administrative, legislative and judicial functions',
        'Constitutional control of administration',
        'Administrative law distinguished from constitutional law',
        'Public and private power',
    ]),
    M('Delegated legislation', [
        'Meaning and need for delegated legislation',
        'Conditional legislation',
        'Essential legislative function',
        'Excessive delegation',
        'Policy, standards and guidance',
        'Sub-delegation',
        'Henry VIII clauses',
        'Retrospective delegated legislation',
        'Judicial control: substantive ultra vires',
        'Judicial control: procedural ultra vires',
        'Legislative control and laying procedures',
        'Publication, consultation and procedural safeguards',
    ]),
    M('Administrative discretion', [
        'Meaning and inevitability of discretion',
        'Scope of judicial review',
        'Mala fides',
        'Improper purpose',
        'Relevant and irrelevant considerations',
        'Non-application of mind',
        'Acting under dictation',
        'Fettering discretion by rigid policy',
        'Unreasonableness and irrationality',
        'Proportionality',
        'Arbitrariness and equality',
        'Failure to exercise discretion',
        'Reasons and transparency',
    ]),
    M('Natural justice', [
        'Purpose and flexible content of natural justice',
        'Rule against bias',
        'Pecuniary, personal, subject-matter and institutional bias',
        'Real likelihood and reasonable apprehension tests',
        'Right to notice',
        'Disclosure of material',
        'Opportunity to present and rebut',
        'Cross-examination and representation',
        'Reasoned decisions',
        'Pre-decisional and post-decisional hearing',
        'Exceptions: urgency, confidentiality and impracticability',
        'Effect of violation and prejudice',
    ]),
    M('Judicial review of administrative action', [
        'Grounds of review: illegality, irrationality and procedural impropriety',
        'Jurisdictional facts and errors of law',
        'Relevant considerations and purpose',
        'Legitimate expectation',
        'Promissory estoppel against government',
        'Proportionality and rights review',
        'Public-law contracts and tenders',
        'Writ remedies and standing',
        'Exclusion or ouster clauses',
        'Remedial discretion, delay and alternative remedy',
    ]),
    M('Right to information', [
        'Constitutional basis of the right to know',
        'Public authority and information',
        'Proactive disclosure',
        'Request procedure and time limits',
        'Exemptions',
        'Public-interest override',
        'Personal information and privacy',
        'Third-party information',
        'Information Commissions',
        'Appeals, penalties and enforcement',
    ]),
    M('Administrative tribunals', [
        'Reasons for specialist adjudication',
        'Advantages and risks of tribunals',
        'Articles 323A and 323B',
        'Independence, tenure and appointments',
        'Procedure and natural justice',
        'Judicial review after L. Chandra Kumar',
        'Central Administrative Tribunal',
        'National Green Tribunal as specialist model',
        'Armed Forces Tribunal and other examples',
        'Tribunal reforms and separation of powers',
    ]),
    M('Commissions of inquiry and vigilance', [
        'Purpose and constitution of commissions of inquiry',
        'Powers and procedure',
        'Evidentiary and legal effect of reports',
        'Fairness to affected persons',
        'Central Vigilance Commission',
        'Vigilance administration and corruption control',
        'Investigative independence and accountability',
    ]),
    M('Regulatory agencies', [
        'Independent regulation and economic governance',
        'Rule-making, licensing and adjudicatory functions',
        'Expertise and democratic accountability',
        'Consultation and reasoned regulation',
        'Regulatory capture',
        'Tariff and market regulation',
        'Appellate mechanisms',
        'Judicial review of expert decisions',
    ]),
    M('Ombudsman and public complaints', [
        'Ombudsman model',
        'Lokpal and Lokayuktas',
        'Jurisdiction and complaint procedure',
        'Investigation and prosecution interfaces',
        'Grievance redress mechanisms',
        'Citizen charters and service guarantees',
        'Whistle-blower protection',
        'Institutional independence and effectiveness',
    ]),
], edition='2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/IVth%20Term_Administrative%20Law_LB%20402_2023.pdf',
   laws=['Constitution of India', 'Right to Information Act, 2005', 'Administrative Tribunals Act, 1985', 'Commissions of Inquiry Act, 1952', 'Central Vigilance Commission Act, 2003', 'Lokpal and Lokayuktas Act, 2013'],
   prereq=['@lb-301.m06','@lb-401.m07','f16'], related=['@lb-4033','@lb-603'], category='Public and regulatory law'),

S('LB-403', 4, 'Labour Law', [
    M('Introduction to labour law', [
        'History and development of labour law',
        'Industrialization and unequal bargaining power',
        'Sociological understanding of employment relations',
        'Labour law as regulation of social power',
        'Protective and collective dimensions of labour law',
        'Marxism and labour law',
        'Constitutional labour rights and Directive Principles',
        'International Labour Organization standards',
        'Transition to the labour codes',
    ]),
    M('Trade unions: definition, registration and recognition', [
        'Trade union and trade-union dispute',
        'Registration requirements',
        'Legal status and incorporation',
        'Rules, office-bearers and membership',
        'Cancellation and appeal',
        'Negotiating union',
        'Negotiating council',
        'Recognition and representativeness',
        'Freedom of association and public employees',
    ]),
    M('Trade-union immunities and funds', [
        'Criminal conspiracy immunity',
        'Civil immunity for acts in contemplation or furtherance of dispute',
        'Limits of immunity',
        'Violence, intimidation and unlawful means',
        'General funds',
        'Political funds',
        'Member rights and accountability',
    ]),
    M('Industry', [
        'Statutory definition of industry',
        'Systematic activity and cooperation',
        'Production or distribution of goods and services',
        'Employer–employee relationship',
        'Profit motive and capital investment',
        'Sovereign functions',
        'Hospitals, education, clubs and professions',
        'Dominant-nature test',
        'Bangalore Water Supply and legislative change',
    ]),
    M('Industrial and individual disputes', [
        'Industrial dispute definition',
        'Parties and community of interest',
        'Employment, non-employment and conditions of labour',
        'Existing and apprehended disputes',
        'Espousal of individual grievance',
        'Deemed industrial disputes',
        'Women and temporary or casual workers',
        'Settlement machinery and access to adjudication',
    ]),
    M('Worker and employee status', [
        'Worker and employee definitions',
        'Contract of service versus contract for services',
        'Control and supervision test',
        'Integration and organization test',
        'Economic reality and multiple-factor approach',
        'Predominant nature of duties',
        'Managerial, administrative and supervisory exclusions',
        'Teachers, professionals and gig workers',
        'Misclassification and sham contracts',
    ]),
    M('Strikes, lockouts and standing orders', [
        'Strike and lockout definitions',
        'Collective concert and cessation of work',
        'Notice requirements',
        'Prohibitions during conciliation and adjudication',
        'Illegal strikes and lockouts',
        'Legality distinguished from justification',
        'Wages for strike period',
        'Right to strike and constitutional limits',
        'Standing orders and service conditions',
        'Certification and model standing orders',
        'Change in service conditions',
    ]),
    M('Lay-off, retrenchment and closure', [
        'Lay-off and inability to provide employment',
        'Compensation and eligibility',
        'Retrenchment and its broad definition',
        'Conditions precedent to retrenchment',
        'Last come, first go',
        'Re-employment of retrenched workers',
        'Permission requirements for larger establishments',
        'Closure and its distinction from lockout',
        'Closure notice and compensation',
        'Transfer of undertaking',
        'Reinstatement, back wages and compensation',
    ]),
    M('Occupational safety and duties', [
        'Scope and registration under the OSHWC Code',
        'Duties of employers',
        'Duties of employees',
        'Rights of employees regarding imminent danger',
        'Safety committees and safety officers',
        'Occupational safety and health standards',
        'Notice and investigation of accidents and disease',
        'Medical examination and records',
        'Contract labour and principal-employer duties',
        'Inter-State migrant workers',
    ]),
    M('Health, welfare, working time and leave', [
        'Cleanliness, ventilation and hazardous processes',
        'Drinking water, sanitation and first aid',
        'Canteens, crèches and welfare officers',
        'Working hours and weekly rest',
        'Overtime',
        'Annual leave with wages',
        'Employment of women and night work safeguards',
        'Young persons and prohibited employment',
        'Inspection, facilitation and penalties',
    ]),
], edition='2026; labour codes', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/LabourLaw-%20LB%20403%20-2026.pdf',
   laws=['Industrial Relations Code, 2020', 'Occupational Safety, Health and Working Conditions Code, 2020', 'Bharatiya Nyaya Sanhita, 2023'],
   prereq=['@lb-102.m07','@lb-401.m09','@lb-402.m03'], related=['@lb-503'], category='Labour and employment law'),

S('LB-404', 4, 'Interpretation of Statutes and Legislative Drafting', [
    M('General concepts', [
        'Kinds of legislation',
        'Interpretation distinguished from construction',
        'Why statutory meaning becomes disputed',
        'Text, context, purpose and consequences',
        'General Clauses Act as a default framework',
        'Definition clauses and statutory conventions',
        'Commencement, repeal and saving',
        'Mandatory and directory provisions',
    ]),
    M('General theories and rules of interpretation', [
        'Court interprets but does not legislate',
        'Statute read as a whole',
        'Ordinary or literal meaning',
        'Golden rule',
        'Mischief rule',
        'Purposive interpretation',
        'Ut res magis valeat quam pereat',
        'Harmonious construction',
        'Strict construction of penal statutes',
        'Strict construction of taxing statutes',
        'Beneficial and remedial construction',
        'Ejusdem generis',
        'Noscitur a sociis',
        'Expressio unius and related maxims',
        'Casus omissus',
        'Prospective and retrospective operation',
        'Presumptions against extra-territoriality and retrospectivity',
        'Constitutional conformity and reading down',
    ]),
    M('Internal and external aids', [
        'Long and short title',
        'Preamble and statement of purpose',
        'Headings and marginal notes',
        'Provisos, explanations and exceptions',
        'Illustrations and schedules',
        'Punctuation',
        'Definition sections',
        'Legislative history and prior law',
        'Statements of objects and reasons',
        'Committee and Law Commission reports',
        'Parliamentary debates',
        'Dictionaries and technical usage',
        'International law and treaties',
        'Foreign judgments and comparative material',
    ]),
    M('Foundations of legislative drafting', [
        'What legislative drafting is',
        'Legislation, policy and legal effect',
        'Constitutional authority and competence',
        'Identifying the mischief and policy objective',
        'Choosing primary or delegated legislation',
        'Legislative scheme and architecture',
        'Definitions and operative provisions',
        'Rights, duties, powers and procedures',
        'Offences, penalties, remedies and appeals',
        'Transition, repeal, saving and commencement',
    ]),
    M('Structure, language and style', [
        'Grammar and punctuation',
        'Subject, predicate and modifiers',
        'Short sentences and one proposition per provision',
        'Conditions, exceptions and provisos',
        'Sections, subsections, clauses and paragraphs',
        'Numbering and cross-references',
        'Logical ordering and grouping',
        'Defined terms and consistency',
        'Incorporation by reference',
        'Schedules, forms and tables',
        'Plain language',
        'Gender-neutral drafting',
        'Avoiding ambiguity, vagueness and redundancy',
        'Drafting an amending Bill',
        'Testing for unintended consequences',
    ]),
], edition='2025 course structure', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/LB-404%20Contents%20Interpretation%20of%20Statutes%20and%20Legislative%20Drafting%202025%20%281%29.pdf', source_status='outline only', source_note='The official file is a six-page course structure rather than a full casebook.',
   laws=['General Clauses Act, 1897', 'Constitution of India'], prereq=['@lb-106.m05','@lb-301.m07','f23'], related=['@lb-4034','@lb-6031'], category='Legal method and drafting'),

S('LB-4031', 4, 'Gender Justice and Feminist Jurisprudence', [
    M('Gender and gender justice', [
        'Sex, gender and social construction',
        'Gender dysphoria',
        'Gender identity and expression',
        'Sexual orientation and LGBTQA+ identities',
        'Private–public dichotomy',
        'Intersectionality',
        'Likelihood of survival and female foeticide',
        'Assigned human worth',
        'Control over property, goods and services',
        'Working conditions and unpaid care',
        'Access to knowledge and information',
        'Participation in political processes',
        'Symbolic representation',
        'Control over body, lifestyle and reproduction',
    ]),
    M('Patriarchy and feminist jurisprudence', [
        'Meaning and institutions of patriarchy',
        'Evolution of patriarchy in India',
        'Effects of patriarchy on women, men and gender minorities',
        'Liberal feminism',
        'Radical feminism',
        'Socialist and Marxist feminism',
        'Individual or I-feminism',
        'Ecofeminism',
        'Cultural feminism',
        'Sameness and difference debate',
        'Formal versus substantive equality',
        'Indian feminist jurisprudence',
        'Postcolonial and intersectional critiques',
    ]),
    M('Third gender and transgender rights', [
        'Person with intersex variations',
        'Transgender person definition',
        'Prohibition of discrimination',
        'Self-identified gender and legal recognition',
        'Certificate procedures and critique',
        'Education rights',
        'Employment rights',
        'Health and welfare duties',
        'Residence and family rights',
        'National Council for Transgender Persons',
        'NALSA and constitutional recognition',
        'Decriminalization of consensual same-sex intimacy',
        'Marriage equality litigation and limits',
        'Critical analysis of the 2019 Act',
    ]),
    M('International instruments on gender justice', [
        'UDHR equality, dignity, privacy, family and work rights',
        'CEDAW basic principles',
        'Direct and indirect discrimination',
        'State obligations under CEDAW',
        'Temporary special measures',
        'Stereotypes and private violence',
        'Impact of CEDAW in Indian law',
        'Yogyakarta Principles 2007',
        'Yogyakarta Principles Plus 10',
        'International norms as interpretive aids',
    ]),
    M('Bodily autonomy, sexuality and consent', [
        'Rape and statutory definition under BNS',
        'Consent, submission and capacity',
        'Aggravated rape and sentencing',
        'Sexual intercourse by husband during separation',
        'Sexual intercourse by person in authority',
        'Sexual intercourse by deceitful means',
        'Gang rape and repeat offenders',
        'Victim identity and reporting restrictions',
        'Sexual harassment, disrobing, voyeurism and stalking',
        'Marital rape exception and constitutional challenge',
        'Development of rape jurisprudence in India',
        'Adultery and decriminalization',
        'Sex work and anti-trafficking law',
        'Obscenity and indecent representation of women',
        'Autonomy, paternalism and carceral feminism',
    ]),
    M('Economic empowerment and workplace equality', [
        'Constitutional equality and women’s work',
        'Protective discrimination and occupational exclusions',
        'Equal opportunity and service conditions',
        'Maternity and care work',
        'Informal labour and social security',
        'Sexual Harassment of Women at Workplace Act, 2013',
        'Internal and Local Committees',
        'Complaint, inquiry and interim measures',
        'Employer prevention duties',
        'Confidentiality and retaliation',
        'Implementation failures and institutional compliance',
    ]),
    M('Reproductive rights', [
        'Reproductive autonomy and constitutional privacy',
        'BNS offences relating to miscarriage and unborn child',
        'Medical Termination of Pregnancy Act framework',
        'Eligibility, gestational limits and medical opinions',
        'Emergency termination',
        'Confidentiality and decisional autonomy',
        'Maternity Benefit Act protections',
        'Pre-Conception and Pre-Natal Diagnostic Techniques Act',
        'Registration and regulation of genetic facilities',
        'Supervisory boards and enforcement',
        'Sex selection, disability and equality critiques',
        'Surrogacy and assisted reproduction as related issues',
    ]),
    M('Violence within family and harmful practices', [
        'Protection of Women from Domestic Violence Act, 2005',
        'Physical, sexual, verbal, emotional and economic abuse',
        'Domestic relationship and shared household',
        'Protection, residence, monetary, custody and compensation orders',
        'Protection officers and service providers',
        'Dowry Prohibition Act, 1961',
        'Dowry harassment and death',
        'Commission of Sati (Prevention) Act, 1987',
        'Devadasi dedication and state laws',
        'Honour crimes and family control',
        'Access to justice and survivor-centred remedies',
    ]),
], edition='2025 course structure', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/Gender%20Justice%20and%20Feminist%20Jurisprudence.pdf', source_status='outline only', source_note='The official file is a short course structure with prescribed statutes and cases.',
   laws=['Constitution of India', 'Transgender Persons (Protection of Rights) Act, 2019', 'Bharatiya Nyaya Sanhita, 2023', 'Sexual Harassment of Women at Workplace Act, 2013', 'Medical Termination of Pregnancy Act, 1971', 'Protection of Women from Domestic Violence Act, 2005', 'Dowry Prohibition Act, 1961'],
   prereq=['@lb-401.m03','@lb-105.m09','@lb-104.m05','@lb-403.m10'], elective=True, category='Gender and equality law'),
]

SUBJECTS += [
S('LB-4032', 4, 'International Institutions', [
    M('Rise and classification of international organizations', [
        'Historical rise of international cooperation',
        'From river commissions and unions to universal organizations',
        'League of Nations and United Nations eras',
        'Definition of an international organization',
        'Intergovernmental organizations distinguished from NGOs',
        'Universal and regional organizations',
        'General and specialist organizations',
        'Open and closed membership',
        'Supranational and intergovernmental features',
        'Constituent treaties and institutional autonomy',
        'India’s historical and contemporary participation',
        'Global South critiques of international institutions',
    ]),
    M('Legal personality and powers', [
        'International legal personality',
        'Objective and relative personality',
        'Constituent instrument as constitutional charter',
        'Express powers',
        'Implied powers',
        'Doctrine of speciality',
        'Capacity to conclude treaties',
        'Capacity to bring international claims',
        'Internal and external legal acts',
        'International organizations and creation of custom',
        'Institutional practice and subsequent practice',
    ]),
    M('Responsibility of international organizations', [
        'Internationally wrongful act of an organization',
        'Attribution to organs and agents',
        'Ultra vires conduct',
        'Breach of international obligation',
        'Aid, assistance, direction and control',
        'Member-state responsibility',
        'Circumstances precluding wrongfulness',
        'Cessation, reparation and guarantees of non-repetition',
        'ILC Articles on Responsibility of International Organizations',
        'Accountability gaps and access to remedies',
    ]),
    M('Privileges and immunities', [
        'Functional necessity',
        'Treaty and headquarters-agreement bases',
        'Immunity from legal process',
        'Premises, archives and communications',
        'Officials and experts on mission',
        'Waiver of immunity',
        'Alternative dispute mechanisms',
        'Employment disputes and due process',
        'Immunity distinguished from responsibility',
    ]),
    M('United Nations and European Union', [
        'UN purposes, principles and membership',
        'General Assembly composition and powers',
        'Security Council composition, voting and powers',
        'Economic and Social Council',
        'Secretariat and Secretary-General',
        'Trusteeship Council and institutional evolution',
        'Budget, peacekeeping and sanctions',
        'EU legal order and founding treaties',
        'European Council, Council, Commission and Parliament',
        'Court of Justice of the European Union',
        'Direct effect, supremacy and conferral',
        'Comparing universal and supranational institutions',
    ]),
    M('International legal institutions', [
        'International Court of Justice: composition',
        'Contentious jurisdiction and consent',
        'Advisory jurisdiction',
        'Admissibility and provisional measures',
        'Judgments, interpretation and enforcement',
        'International Criminal Court: Rome Statute structure',
        'Subject-matter jurisdiction',
        'Territorial, nationality and Security Council triggers',
        'Complementarity and admissibility',
        'Prosecutor, Pre-Trial, Trial and Appeals Chambers',
        'Cooperation, arrest and enforcement challenges',
        'Institutional legitimacy and selectivity critiques',
    ]),
], edition='2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/IVth%20Term_International%20Institution_LB4032_2023.pdf',
   laws=['Charter of the United Nations', 'Statute of the International Court of Justice', 'Rome Statute of the International Criminal Court', 'Treaty on European Union'],
   prereq=['@lb-205.m07'], elective=True, category='International law'),

S('LB-4033', 4, 'Competition Law', [
    M('Introduction and institutional development', [
        'Competition, market power and consumer welfare',
        'Constitutional and Directive Principle context',
        'Economic liberalization and need for modern competition law',
        'MRTP Act experience',
        'Raghavan Committee',
        'Competition Act objectives and scheme',
        'Competition law distinguished from consumer protection and sector regulation',
        'Comparative overview of EU and US law',
        'Competition Commission of India',
        'Director General investigation',
        'National Company Law Appellate Tribunal and Supreme Court review',
        'Penalties, remedies and due process',
    ]),
    M('Core definitions and market analysis', [
        'Agreement',
        'Cartel',
        'Consumer',
        'Enterprise and group',
        'Goods and services',
        'Practice and association of enterprises',
        'Relevant product market',
        'Relevant geographic market',
        'Demand and supply substitution',
        'Market share and concentration',
        'Turnover and relevant turnover',
        'Appreciable adverse effect on competition',
    ]),
    M('Anti-competitive agreements', [
        'Horizontal and vertical agreements',
        'Agreement without formal contract',
        'Presumption against specified horizontal agreements',
        'Price fixing',
        'Output or supply limitation',
        'Market allocation',
        'Bid rigging and collusive bidding',
        'Cartels and hub-and-spoke arrangements',
        'Buyers’ cartels',
        'Rule of reason and balancing factors',
        'Tie-in arrangements',
        'Exclusive supply and distribution',
        'Refusal to deal',
        'Resale price maintenance',
        'Efficiency and joint-venture exceptions',
        'Intellectual-property exception',
        'Export exception',
    ]),
    M('Dominant position and abuse', [
        'Dominance distinguished from monopoly',
        'Determining relevant market',
        'Factors showing dominant position',
        'Unfair or discriminatory conditions and prices',
        'Predatory pricing',
        'Limiting production, markets or technical development',
        'Denial of market access',
        'Supplementary obligations',
        'Leveraging dominance into another market',
        'Essential-facilities doctrine',
        'Margin squeeze and refusal to supply',
        'Collective dominance and statutory limits',
        'Objective justification and remedies',
    ]),
    M('Combinations and merger control', [
        'Acquisition, merger and amalgamation',
        'Control and material influence',
        'Thresholds and exemptions',
        'Notification and standstill obligation',
        'Green-channel and expedited review',
        'Horizontal, vertical and conglomerate effects',
        'Unilateral and coordinated effects',
        'Entry barriers and countervailing power',
        'Failing-firm and efficiency arguments',
        'Remedies, modifications and prohibition',
        'Gun jumping and penalties',
        'Deal-value thresholds and digital acquisitions',
    ]),
    M('Leniency, settlement, commitment and advocacy', [
        'Lesser-penalty programme',
        'First applicant and added value',
        'Confidentiality and disclosure',
        'Dawn raids and evidence preservation',
        'Settlement and commitment mechanisms',
        'Compensation claims',
        'Competition advocacy',
        'Government policy and competitive neutrality',
        'Interface with sector regulators',
    ]),
    M('Emerging competition issues', [
        'Digital platforms and multi-sided markets',
        'Network effects and data advantages',
        'Self-preferencing',
        'Most-favoured-nation clauses',
        'Algorithmic pricing and tacit coordination',
        'Killer acquisitions',
        'Attention and zero-price markets',
        'Big data, privacy and competition',
        'Labour-market monopsony',
        'Sustainability agreements',
        'Competition Amendment Act developments',
    ]),
], edition='2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/IVth%20Term_Competition%20Law_LB4033_2023.pdf',
   laws=['Competition Act, 2002', 'Competition (Amendment) Act, 2023'],
   prereq=['@lb-303.m09','@lb-402.m09','@lb-102.m07'], elective=True, category='Competition and economic regulation'),

S('LB-4034', 4, 'Legislative Drafting (Old)', [
    M('Legislation and legislative scheme', [
        'Nature and purpose of legislative drafting',
        'Meaning and forms of legislation',
        'Parliamentary style and institutional conventions',
        'Constitutional competence',
        'Policy instructions and drafting instructions',
        'Identifying the legal mischief',
        'Choice of regulatory technique',
        'Designing the legislative scheme',
        'Primary and delegated provisions',
        'Commencement, application and extent',
        'Enforcement and review architecture',
    ]),
    M('Language, structure and style', [
        'Grammar and punctuation',
        'Principal subject and predicate',
        'Modifiers and ambiguity',
        'Main and subordinate clauses',
        'Common legislative phrases',
        'Conditions, exceptions, provisos and explanations',
        'Sections, subsections, paragraphs and subparagraphs',
        'Numbering and lettering',
        'Cross-references and incorporation by reference',
        'Grouping, sequence and outline',
        'Definitions and consistency',
        'Plain language and readability',
        'Gender-neutral language',
        'Avoiding archaism, nominalization and double negatives',
    ]),
    M('Interpretation-aware drafting', [
        'Literal, golden and mischief approaches',
        'Purposive interpretation',
        'Harmonious construction',
        'Ejusdem generis and noscitur a sociis',
        'Internal aids created by drafting',
        'External aids and legislative history',
        'Interpretation Acts and default rules',
        'Presumptions about retrospectivity and rights',
        'Mandatory and directory language',
        'Drafting to reduce judicial uncertainty',
    ]),
    M('Constitutional constraints on drafting', [
        'Legislative competence and federal lists',
        'Fundamental rights review',
        'Equality and non-arbitrariness',
        'Speech, liberty and proportionality',
        'Delegation and essential legislative function',
        'Taxing and penal provisions',
        'Procedural fairness and hearing rights',
        'Exclusion clauses and judicial review',
        'Retrospective legislation',
        'Severability and reading down',
    ]),
], edition='2023 old course', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/IV%20TERM_LEGISLATIVE%20DRAFTING_LB-4034_2023.pdf', source_status='official archive',
   laws=['Constitution of India', 'General Clauses Act, 1897'], prereq=['@lb-404.m05'], elective=True, related=['@lb-404'], category='Legal drafting'),

S('LB-4035', 4, 'Humanitarian Law and Refugee Law', [
    M('Introduction to international humanitarian law', [
        'Definition and purpose of IHL',
        'Historical development and the Hague–Geneva traditions',
        'Sources of IHL',
        'Treaty and customary IHL',
        'International and non-international armed conflict',
        'Threshold and classification of conflict',
        'Occupation',
        'IHL distinguished from jus ad bellum',
        'Relationship between IHL and human-rights law',
        'Martens clause',
    ]),
    M('Protection of persons hors de combat', [
        'Wounded and sick on land',
        'Wounded, sick and shipwrecked at sea',
        'Medical personnel, units and transports',
        'Distinctive emblems',
        'Prisoner-of-war status',
        'Treatment and judicial guarantees of prisoners',
        'Civilians in enemy hands',
        'Internment and occupied territory',
        'Women, children and other specially protected persons',
        'Missing persons and the dead',
    ]),
    M('Methods and means of warfare', [
        'Principle of distinction',
        'Combatants and civilians',
        'Military objectives and civilian objects',
        'Direct participation in hostilities',
        'Proportionality in attack',
        'Precautions in attack and against effects',
        'Indiscriminate attacks',
        'Prohibited weapons and unnecessary suffering',
        'Perfidy and ruses of war',
        'Cultural property',
        'Natural environment',
        'Siege, starvation and humanitarian relief',
        'Cyber operations and autonomous weapons as emerging issues',
    ]),
    M('International and hybrid criminal tribunals', [
        'Nuremberg and Tokyo tribunals',
        'Individual criminal responsibility',
        'War crimes, crimes against humanity and genocide',
        'International Criminal Tribunal for the former Yugoslavia',
        'International Criminal Tribunal for Rwanda',
        'Hybrid and internationalized courts',
        'Command responsibility',
        'Superior orders and defences',
        'Legacy, selectivity and due-process critiques',
    ]),
    M('International Criminal Court', [
        'Rome Statute institutions',
        'Subject-matter jurisdiction',
        'Territorial and nationality jurisdiction',
        'State referral, Security Council referral and proprio motu investigation',
        'Temporal jurisdiction',
        'Complementarity',
        'Gravity and admissibility',
        'Elements of crimes and modes of liability',
        'Cooperation and surrender',
        'Victim participation and reparations',
        'Immunities and head-of-state questions',
    ]),
    M('Refugee law: concepts and development', [
        'Refugee, asylum seeker, migrant and internally displaced person',
        'Historical development of international refugee protection',
        '1951 Convention and 1967 Protocol',
        'Regional refugee definitions',
        'Persecution and well-founded fear',
        'Convention grounds',
        'Agents of persecution and state protection',
        'Internal flight or relocation alternative',
        'Mass influx and temporary protection',
    ]),
    M('Refugee status and protection', [
        'Inclusion clauses',
        'Exclusion for serious crimes and acts contrary to UN purposes',
        'Cessation clauses',
        'Non-refoulement',
        'Direct and indirect refoulement',
        'Exceptions and human-rights limits',
        'Non-penalization for illegal entry',
        'Rights to courts, work, education and welfare',
        'Identity and travel documents',
        'Duties of refugees',
        'Status determination and procedural fairness',
    ]),
    M('Durable solutions', [
        'Voluntary repatriation',
        'Safety, dignity and informed choice',
        'Local integration',
        'Naturalization and long-term residence',
        'Third-country resettlement',
        'Complementary pathways',
        'Burden and responsibility sharing',
        'Protracted refugee situations',
    ]),
    M('UNHCR', [
        'Mandate and Statute of UNHCR',
        'International protection function',
        'Supervision of the Refugee Convention',
        'Status determination under mandate',
        'Assistance, registration and documentation',
        'Emergency response and coordination',
        'Durable-solution role',
        'Relationship with host states and NGOs',
        'Limits of mandate and funding',
    ]),
    M('Refugee protection in India', [
        'Absence of a dedicated refugee statute',
        'Foreigners Act and passport framework',
        'Constitutional protection of life and equality for non-citizens',
        'Judicial use of non-refoulement',
        'Treaty obligations and customary-law arguments',
        'UNHCR role in India',
        'Different treatment of refugee groups',
        'Detention, deportation and national-security claims',
        'Citizenship and long-term solutions',
        'Need and models for domestic refugee legislation',
    ]),
], edition='2022/2023 official archive', source='https://lawfaculty.du.ac.in/old-lawfaculty/files/LLB/LLBCM23/IVth%20Term_Humanitarian%20and%20Refugee%20Law_LB%204035_2023.pdf', source_status='best available official archive', source_note='The current catalog link was unavailable; this older official DU archive is the best available source.',
   laws=['Geneva Conventions of 1949', 'Additional Protocols of 1977', 'Rome Statute of the International Criminal Court', 'Convention relating to the Status of Refugees, 1951', 'Protocol relating to the Status of Refugees, 1967', 'Foreigners Act, 1946'],
   prereq=['@lb-205.m07','@lb-4032.m06'], elective=True, category='International humanitarian and refugee law'),

S('LB-4036', 4, 'Intellectual Property Rights Law I', [
    M('Introduction to intellectual property and abuse', [
        'Nature and concept of intellectual property rights',
        'Justifications: incentive, labour, personality and development',
        'Types of intellectual property',
        'Territoriality and limited duration',
        'WTO and TRIPS framework',
        'National enforcement of IPR',
        'Civil, criminal and border remedies',
        'Abuse and overreach of intellectual property',
        'Competition and public-interest limits',
        'Paris Convention',
        'Madrid Agreement and Protocol',
        'Reciprocity and priority',
        'Minimum standards',
        'National treatment',
        'Most-favoured-nation treatment',
    ]),
    M('Trade marks: subject matter and registration', [
        'Mark, trademark, goods and services',
        'Registered and unregistered marks',
        'Functions and need for trademark protection',
        'Use in relation to goods, services and advertising',
        'Service marks',
        'Domain names as trademarks',
        'Application and registration procedure',
        'Absolute grounds for refusal',
        'Distinctiveness and descriptiveness',
        'Generic and customary marks',
        'Acquired distinctiveness',
        'Deceptive or scandalous marks',
        'Relative grounds for refusal',
        'Similarity, confusion and association',
        'Earlier and well-known trademarks',
        'Honest concurrent use',
        'Prior user and vested rights',
        'Rectification and cancellation',
    ]),
    M('Trade marks: infringement, passing off and exploitation', [
        'Infringement of registered trademarks',
        'Identity or similarity of marks and goods',
        'Infringement for dissimilar goods by reputed marks',
        'Passing off and goodwill',
        'Misrepresentation and damage',
        'Transborder reputation',
        'Infringement distinguished from passing off',
        'Statutory exceptions and descriptive use',
        'Trade-mark dilution',
        'Blurring and tarnishment',
        'Trade dress and colour combinations',
        'Comparative advertising and disparagement',
        'Use in advertising',
        'Exhaustion and parallel imports',
        'Licensing and registered users',
        'Quality control and assignment',
        'Civil remedies and interlocutory relief',
    ]),
    M('Geographical indications', [
        'Geographical indication, indication, goods and producer',
        'Indication of source and appellation of origin',
        'Community and collective rights',
        'GI distinguished from certification and collective marks',
        'Registration procedure',
        'Grounds for refusal',
        'Homonymous indications',
        'Authorized users',
        'Duration and renewal',
        'Infringement',
        'Penalties and remedies',
        'Conflicts between GIs and trademarks',
        'GI logo, quality control and development concerns',
    ]),
    M('Industrial designs', [
        'Need for design protection',
        'Design and article',
        'New or original design',
        'Features judged solely by the eye',
        'Exclusions for function and prior publication',
        'Registration procedure',
        'Duration of design copyright',
        'Cancellation',
        'Piracy or infringement',
        'Remedies',
        'Overlap of design, copyright and trademark protection',
        'Spare parts and market competition',
    ]),
], edition='2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/IVth%20Term_Intellectual%20Property%20Rights%20Law_LB%204036_2023.pdf',
   laws=['Trade Marks Act, 1999', 'Geographical Indications of Goods (Registration and Protection) Act, 1999', 'Designs Act, 2000', 'TRIPS Agreement'],
   prereq=['@lb-102.m07','@lb-103.m08','@lb-301.m07'], elective=True, related=['@lb-5037'], category='Intellectual property law'),
]

# Term V ----------------------------------------------------------------------
SUBJECTS += [
S('LB-501', 5, 'Moot Court, Mock Trial and Internship', [
    M('Client interviewing and counselling', [
        'Preparing for the first client conference',
        'Building rapport and explaining confidentiality',
        'Open, closed and funnel questions',
        'Listening, clarification and avoiding assumptions',
        'Identifying client goals and constraints',
        'Separating facts, beliefs and legal conclusions',
        'Conflict and competence checks',
        'Chronology and document collection',
        'Explaining options, cost, delay and risk',
        'Obtaining informed instructions',
        'Conference note and follow-up plan',
    ]),
    M('Case analysis and theory', [
        'Material-fact chronology',
        'Parties, forum and procedural posture',
        'Cause of action, offence or defence',
        'Issue tree',
        'Elements and burden map',
        'Proof chart and evidentiary gaps',
        'Authority hierarchy and research plan',
        'Theme and theory of the case',
        'Alternative theories and weak points',
        'Relief or order sought',
        'Ethical limits on case theory',
    ]),
    M('Mock trial: preparation and openings', [
        'Trial file and witness order',
        'Theory translated into admissible proof',
        'Stipulations and preliminary applications',
        'Preparing a witness without coaching false evidence',
        'Exhibits and foundation',
        'Opening statement structure',
        'Story, burden and promised proof',
        'Avoiding argument in opening',
        'Courtroom etiquette and record management',
    ]),
    M('Examination-in-chief', [
        'Purpose and structure of examination-in-chief',
        'Witness orientation and competence',
        'Non-leading questions',
        'Personal knowledge',
        'Refreshing memory',
        'Introducing documents and objects',
        'Hearsay and other objections',
        'Transitions and chronological clarity',
        'Handling an adverse or forgetful witness',
        'Rehabilitation after objections',
    ]),
    M('Cross-examination and re-examination', [
        'Goals of cross-examination',
        'Leading questions and one fact per question',
        'Control, pace and sequence',
        'Impeachment by prior inconsistent statement',
        'Bias, interest, perception and memory',
        'Challenging expert testimony',
        'Putting the case to the witness',
        'Avoiding open-ended and risky questions',
        'Ethical limits and harassment',
        'Re-examination confined to matters arising',
    ]),
    M('Final submissions and trial orders', [
        'Closing submission tied to elements and burden',
        'Using admitted evidence and reasonable inference',
        'Addressing adverse facts',
        'Credibility submissions',
        'Law and precedent in trial argument',
        'Reply and sur-reply limits',
        'Written submissions and proposed orders',
        'Costs, sentence or remedy submissions',
    ]),
    M('Moot problem and memorial research', [
        'Reading the moot proposition and clarifications',
        'Identifying stipulated and disputed facts',
        'Jurisdiction and maintainability',
        'Framing issues',
        'Research log and authority verification',
        'Primary and secondary authorities',
        'Comparative and international materials',
        'Record citations',
        'Building arguments for both sides',
        'Testing concessions and limiting principles',
    ]),
    M('Memorial writing', [
        'Cover, table of contents and abbreviations',
        'Index of authorities',
        'Statement of jurisdiction',
        'Statement of facts and advocacy limits',
        'Issues presented',
        'Summary of arguments',
        'Arguments advanced',
        'Issue-rule-application-conclusion structure',
        'Footnotes, citations and pinpoints',
        'Prayer for relief',
        'Formatting, word limits and anonymity',
        'Editing for consistency and source support',
    ]),
    M('Moot oral advocacy', [
        'Road map and requested relief',
        'Division of issues between speakers',
        'Time allocation',
        'Using a compendium and record',
        'Answering judicial questions directly',
        'Distinguishing adverse authorities',
        'Concessions and preserving the case',
        'Rebuttal and sur-rebuttal',
        'Court etiquette and teamwork',
        'Feedback and deliberate practice',
    ]),
    M('Internship, court visit and chamber placement', [
        'Choosing placement and setting learning goals',
        'Professional conduct and punctuality',
        'Confidentiality and data security',
        'Court hierarchy and daily cause list',
        'Observing filing, mentioning and hearing stages',
        'Maintaining a court-visit diary',
        'Case briefing and research assignments',
        'Drafting under supervision',
        'File organization and limitation diary',
        'Client conferences and ethical observation',
        'Reflective internship diary',
        'Supervisor feedback and final report',
    ]),
], edition='2025 best available', source=CATALOG_URL, source_status='best available official course material', source_note='The exact 2026–27 linked file was unavailable. The complete official 2025 DU material is used as the best available edition.',
   laws=['Bar Council of India Rules', 'Code of Civil Procedure, 1908', 'Bharatiya Nagarik Suraksha Sanhita, 2023', 'Bharatiya Sakshya Adhiniyam, 2023'],
   prereq=['f21','f24','f25','@lb-201.m05','@lb-203.m08','@lb-302.m14'], category='Clinical legal education'),

S('LB-502', 5, 'Drafting, Pleading and Conveyance', [
    M('Principles of pleadings', [
        'Purpose and function of pleadings',
        'Material facts versus evidence',
        'Concise form and numbered paragraphs',
        'Cause of action and jurisdictional facts',
        'Specific pleading of fraud, misrepresentation and undue influence',
        'Alternative and inconsistent pleas',
        'Admissions, denials and non-traverse',
        'Verification and supporting affidavit',
        'Documents relied on',
        'Relief and valuation',
        'Amendment and ethical responsibility',
    ]),
    M('Civil plaint', [
        'Title and description of court',
        'Parties and addresses for service',
        'Jurisdiction paragraph',
        'Chronological material facts',
        'Cause of action',
        'Limitation statement',
        'Valuation and court fee',
        'Reliefs and alternative relief',
        'Interim-relief prayer',
        'Verification, affidavit and list of documents',
    ]),
    M('Written statement and counterclaim', [
        'Preliminary objections',
        'Specific admissions and denials',
        'Traverse of each material allegation',
        'Affirmative defences',
        'Set-off',
        'Counterclaim',
        'Limitation and jurisdiction objections',
        'Documents and verification',
        'Replication and limits on new pleas',
    ]),
    M('Civil applications and appellate pleadings', [
        'Temporary injunction application',
        'Application for amendment',
        'Application for impleadment',
        'Application to set aside ex parte decree',
        'Execution petition',
        'Caveat',
        'Memorandum of first appeal',
        'Second appeal and substantial question of law',
        'Revision petition',
        'Review petition',
        'Written submissions and proposed order',
    ]),
    M('Constitutional and public-law pleadings', [
        'Writ petition under Article 226',
        'Petition under Article 32',
        'Parties and public authorities',
        'Locus and maintainability',
        'Delay and alternative remedy',
        'Statement of constitutional or statutory violation',
        'Grounds for judicial review',
        'Interim protection',
        'Affidavits and annexures',
        'Counter-affidavit and rejoinder',
        'Public-interest litigation safeguards',
    ]),
    M('Criminal pleadings', [
        'Criminal complaint',
        'Application for registration or investigation',
        'Regular bail application',
        'Anticipatory bail application',
        'Default-bail application',
        'Application for discharge',
        'Criminal revision',
        'Criminal appeal',
        'Petition for quashing',
        'Suspension of sentence',
        'Victim protest petition and compensation request',
    ]),
    M('Affidavits, notices and opinions', [
        'Affidavit based on personal knowledge and information',
        'Verification and source disclosure',
        'Legal notice',
        'Reply to legal notice',
        'Demand and cure periods',
        'Case opinion and advice note',
        'Facts, questions, law, analysis and recommendation',
        'Conflict, assumption and qualification statements',
        'Chronology and document index',
    ]),
    M('Conveyancing fundamentals', [
        'Instrument, deed and conveyance',
        'Title investigation and chain of title',
        'Parties, recitals and operative clauses',
        'Consideration and receipt',
        'Description of property',
        'Representations, covenants and indemnities',
        'Conditions precedent and subsequent',
        'Possession, risk and completion',
        'Stamping and registration',
        'Execution, attestation and witnesses',
        'Schedules and annexures',
    ]),
    M('Property and commercial instruments', [
        'Agreement to sell',
        'Sale deed',
        'Mortgage deed',
        'Lease deed',
        'Leave-and-licence agreement',
        'Gift deed',
        'Release and relinquishment deed',
        'Partition deed',
        'Power of attorney',
        'Promissory note and acknowledgment of debt',
        'Partnership deed',
        'Trust deed',
    ]),
    M('Succession and settlement instruments', [
        'Will and testamentary capacity',
        'Appointment of executor',
        'Specific and residuary bequests',
        'Attestation of will',
        'Codicil',
        'Family settlement',
        'Adoption deed and related declarations',
        'Nomination distinguished from succession',
        'Revocation and safekeeping',
    ]),
], edition='2025', source='https://lawfaculty.du.ac.in/userfiles/downloads/Drafting%20case%20material%20-2025.pdf',
   laws=['Code of Civil Procedure, 1908', 'Bharatiya Nagarik Suraksha Sanhita, 2023', 'Transfer of Property Act, 1882', 'Registration Act, 1908', 'Indian Stamp Act, 1899', 'Indian Succession Act, 1925'],
   prereq=['f23','@lb-302.m15','@lb-203.m10','@lb-204.m12'], related=['@lb-501','@lb-6034'], category='Clinical legal education'),

S('LB-503', 5, 'Industrial Law', [
    M('Industrial-dispute settlement agencies', [
        'Works committees',
        'Conciliation officers',
        'Boards of conciliation',
        'Courts of inquiry',
        'Labour Courts',
        'Industrial Tribunals',
        'National Tribunals',
        'Jurisdiction and subject allocation',
        'Voluntary arbitration',
        'Government intervention and institutional delay',
    ]),
    M('Reference of industrial disputes', [
        'Existing or apprehended dispute',
        'Appropriate government',
        'Administrative nature of reference decision',
        'Duty to record reasons for refusal',
        'Delay and stale disputes',
        'Scope of adjudication under terms of reference',
        'Incidental issues',
        'Correction and amendment of reference',
        'Judicial review of reference',
    ]),
    M('Awards and settlements', [
        'Settlement in and outside conciliation',
        'Nature and publication of award',
        'Commencement and enforceability',
        'Period of operation',
        'Termination',
        'Persons bound',
        'Binding effect on successors and future employees',
        'Consent awards',
        'Interpretation and implementation',
        'Recovery of money due',
    ]),
    M('Managerial prerogative and discipline', [
        'Managerial control and certified standing orders',
        'Misconduct and service rules',
        'Charge-sheet',
        'Suspension pending inquiry',
        'Domestic inquiry',
        'Natural justice in disciplinary process',
        'Representation and cross-examination',
        'Findings and standard of proof',
        'Past record and proportionality',
        'Victimization and unfair labour practice',
        'Loss of confidence',
    ]),
    M('Adjudicatory power over dismissal', [
        'Section 11A power to reappraise evidence',
        'Defective or absent domestic inquiry',
        'Employer’s opportunity to prove misconduct',
        'Proportionality of punishment',
        'Reinstatement',
        'Back wages',
        'Compensation instead of reinstatement',
        'Gainful employment and mitigation',
    ]),
    M('Protection during pending proceedings', [
        'Purpose of sections 33 and 33A',
        'Connected and unconnected misconduct',
        'Alteration of service conditions',
        'Dismissal or punishment during pendency',
        'Approval and permission requirements',
        'Protected workmen',
        'Complaint for contravention',
        'Effect of non-compliance',
    ]),
    M('Wages and wage fixation', [
        'Meaning and components of wages',
        'Minimum wage',
        'Fair wage',
        'Living wage',
        'Need-based minimum wage',
        'Capacity to pay',
        'Industry-cum-region principle',
        'Dearness allowance and neutralization',
        'Wage boards and adjudication',
        'Equal remuneration',
        'Code on Wages transition',
    ]),
    M('Employees’ compensation', [
        'Employer liability for personal injury',
        'Accident arising out of and in course of employment',
        'Notional extension',
        'Occupational disease',
        'Disablement and dependency',
        'Calculation and distribution of compensation',
        'Notice and claims',
        'Contracting and indemnity',
        'Commissioner’s jurisdiction',
    ]),
    M('Employees’ State Insurance', [
        'Coverage and contribution',
        'Employees’ State Insurance Corporation',
        'Sickness and maternity benefits',
        'Disablement and dependants’ benefits',
        'Medical benefit',
        'Employment injury',
        'Bar of other remedies',
        'ESI Court and disputes',
    ]),
    M('Bonus, gratuity and social security', [
        'Eligibility and allocable surplus for bonus',
        'Minimum and maximum bonus',
        'Set-on and set-off',
        'Disqualification and recovery',
        'Gratuity eligibility and continuous service',
        'Calculation and forfeiture',
        'Nomination and payment',
        'Maternity benefit',
        'Provident fund and pension overview',
        'Social Security Code framework',
        'Gig and platform workers',
    ]),
], edition='2025 compilation; legacy statutes with code transition', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/LB-503%20Industrial-Law-including-IDRA.pdf',
   laws=['Industrial Disputes Act, 1947', 'Industrial Employment (Standing Orders) Act, 1946', 'Code on Wages, 2019', 'Code on Social Security, 2020', 'Employees’ Compensation Act, 1923', 'Employees’ State Insurance Act, 1948'],
   prereq=['@lb-403.m10'], related=['@lb-403'], category='Labour and social-security law'),

S('LB-5031', 5, 'Information Technology Law', [
    M('Cyber law and the Information Technology Act', [
        'Cyberspace, networks and digital communication',
        'Need and objectives of cyber law',
        'UNCITRAL Model Law background',
        'Scope and application of the Information Technology Act, 2000',
        'Key statutory definitions',
        'Electronic governance',
        'Legal recognition of electronic records',
        'Retention and publication of electronic records',
        'Exclusions from the Act',
        'Extra-territorial application',
    ]),
    M('Electronic records and signatures', [
        'Electronic and digital signatures',
        'Asymmetric cryptosystems and hash functions',
        'Authentication of electronic records',
        'Secure electronic records and signatures',
        'Attribution of electronic records',
        'Acknowledgment of receipt',
        'Time and place of dispatch and receipt',
        'Controller and certifying authorities',
        'Electronic signature certificates',
        'Subscriber duties and compromise',
    ]),
    M('Civil liability, data and online harm', [
        'Unauthorized access and damage to computer resources',
        'Data theft and disruption',
        'Compensation and adjudication',
        'Failure to protect data and reasonable security practices',
        'Breach of confidentiality and privacy',
        'Online defamation',
        'Doxxing, impersonation and identity harms',
        'Constitutional privacy and informational self-determination',
        'Digital Personal Data Protection Act interface',
        'Platform terms and private governance',
    ]),
    M('Cyber offences and electronic evidence', [
        'Computer-related offences',
        'Identity theft',
        'Cheating by personation using computer resources',
        'Violation of privacy',
        'Cyber terrorism',
        'Obscene and sexually explicit electronic material',
        'Child sexual-abuse material',
        'Attempt, abetment and company liability',
        'Search, seizure and investigation',
        'Jurisdiction for cyber offences',
        'Electronic evidence and authentication',
        'Logs, metadata, hash values and chain of custody',
    ]),
    M('Intermediary liability', [
        'Intermediary and safe harbour',
        'Actual knowledge and court or government orders',
        'Due diligence',
        'Grievance redressal',
        'Significant social-media intermediaries',
        'Traceability and encryption concerns',
        'Content moderation and private censorship',
        'Copyright and trademark notices',
        'Marketplace and platform liability',
        'Constitutional limits on blocking and takedown',
    ]),
    M('Cybersecurity and state powers', [
        'Protected systems and critical information infrastructure',
        'CERT-In functions and incident reporting',
        'Interception, monitoring and decryption',
        'Blocking public access to information',
        'Traffic-data monitoring',
        'Cybersecurity directions and compliance',
        'Encryption and lawful access',
        'Surveillance, necessity and proportionality',
        'Incident response, preservation and breach notification',
    ]),
    M('Electronic contracts', [
        'Formation of contracts through electronic means',
        'Clickwrap, browsewrap and online terms',
        'Automated contracts and electronic agents',
        'Attribution and authority',
        'Electronic signatures and enforceability',
        'Consumer consent and dark patterns',
        'Choice of law and forum clauses',
        'Smart contracts and code-based performance',
    ]),
    M('Intellectual property online', [
        'Domain-name system and cybersquatting',
        'Trademark infringement in domain names',
        'Uniform Domain Name Dispute Resolution Policy',
        'Copyright in websites and software',
        'Linking, framing and caching',
        'Digital rights management and circumvention',
        'Open-source licences',
        'Platform notice-and-takedown',
    ]),
    M('Jurisdiction in cyberspace', [
        'Territoriality and online conduct',
        'Place of cause of action',
        'Targeting and purposeful availment',
        'Effects doctrine',
        'Personal jurisdiction over foreign defendants',
        'Choice of law',
        'Forum-selection clauses',
        'Cross-border investigation and data access',
        'Enforcement of online judgments and orders',
    ]),
], edition='2026', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/CMITLAW2026.pdf',
   laws=['Information Technology Act, 2000', 'Information Technology Rules', 'Digital Personal Data Protection Act, 2023', 'Bharatiya Nyaya Sanhita, 2023', 'Bharatiya Sakshya Adhiniyam, 2023'],
   prereq=['@lb-102.m11','@lb-201.m03','@lb-104.m08','@lb-401.m03'], elective=True, category='Technology law'),

S('LB-5033', 5, 'Criminology', [
    M('Concept, scope and history of criminology', [
        'Crime as legal and social construct',
        'Criminology, penology and criminal justice',
        'Scope and methods of criminological inquiry',
        'Official statistics and dark figure of crime',
        'Crime, deviance and social control',
        'Classical school',
        'Positivist school',
        'Biological and psychological explanations',
        'Sociological turn in criminology',
        'Crime and the criminal as changing categories',
    ]),
    M('Theories of crime', [
        'Classical rational-choice theory',
        'Positivism and determinism',
        'Differential association',
        'Social disorganization',
        'Durkheim and anomie',
        'Merton’s strain theory',
        'Control theories',
        'Labelling theory',
        'Freud and psychoanalytic explanations',
        'Conflict and radical criminology',
        'Bonger and economic conditions',
        'Feminist criminology',
        'Life-course and developmental perspectives',
        'Routine-activity theory',
    ]),
    M('Crime in India', [
        'Using NCRB and other crime data',
        'Limits of police-recorded statistics',
        'Violent and property crime',
        'Caste and communal violence',
        'Crimes against women and children',
        'Organized crime',
        'White-collar and corporate crime',
        'Cybercrime',
        'Terrorism and state response',
        'Victimless and moral-regulation offences',
        'Regional, class and gender patterns',
    ]),
    M('Juvenile justice', [
        'Theories of juvenile offending',
        'Child in conflict with law',
        'Age determination',
        'Juvenile Justice Board',
        'Apprehension, bail and inquiry',
        'Heinous offences and preliminary assessment',
        'Transfer to Children’s Court',
        'Institutional and non-institutional measures',
        'Rehabilitation and social reintegration',
        'Children in need of care and protection',
        'Restorative and child-rights critique',
    ]),
    M('Punishment and sentencing', [
        'Retributive theory',
        'Deterrent theory',
        'Preventive or incapacitative theory',
        'Reformative theory',
        'Restorative justice',
        'Proportionality',
        'Sentencing discretion and disparity',
        'Aggravating and mitigating factors',
        'Death penalty and rarest-of-rare doctrine',
        'Life imprisonment and remission',
        'Community service and alternatives',
        'Victim impact and individualized sentencing',
    ]),
    M('Victimology', [
        'Development and scope of victimology',
        'Primary, secondary and repeat victimization',
        'Victim precipitation theories and critiques',
        'Rights to information, participation and protection',
        'Victim compensation',
        'Restitution and reparation',
        'Witness protection',
        'Restorative justice and mediation',
        'Victims of state and corporate crime',
        'Trauma-informed justice',
    ]),
    M('Police', [
        'History and organization of policing in India',
        'Police powers of arrest, search and investigation',
        'Discretion and street-level bureaucracy',
        'Custodial violence and deaths',
        'Bias, profiling and vulnerable communities',
        'Police accountability mechanisms',
        'Police complaints authorities',
        'Supreme Court police-reform directions',
        'Forensic capacity and technology',
        'Community policing and legitimacy',
    ]),
    M('Prisons and correction', [
        'History and purposes of imprisonment',
        'Types of prisons and prisoners',
        'Prison administration',
        'Prisoners’ fundamental rights',
        'Undertrial detention and overcrowding',
        'Health, mental health and sanitation',
        'Women, children and transgender prisoners',
        'Solitary confinement and discipline',
        'Open prisons',
        'Parole, furlough and remission',
        'Probation and community corrections',
        'Aftercare and reintegration',
        'Prison reform committees and model prison law',
    ]),
], edition='2025', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/Criminology-2025_compressed.pdf',
   laws=['Bharatiya Nyaya Sanhita, 2023', 'Juvenile Justice (Care and Protection of Children) Act, 2015', 'Probation of Offenders Act, 1958', 'Prisons Act, 1894'],
   prereq=['@lb-104.m10','@lb-203.m10'], elective=True, category='Criminology and criminal justice'),
]

# Term V (continued) -----------------------------------------------------------
SUBJECTS += [
S('LB-5034', 5, 'International Trade Law', [
    M('Origin and evolution of GATT and the WTO', [
        'Global economics and the role of international trade law',
        'Protectionism and free-trade theories',
        'Havana Charter and the birth of GATT 1947',
        'GATT negotiation rounds',
        'Uruguay Round and GATT 1994',
        'Agreement Establishing the World Trade Organization',
        'WTO agreements, annexes and membership',
        'Objectives, functions and institutional structure of the WTO',
        'Decision-making, voting, amendment and waiver',
    ]),
    M('WTO dispute settlement', [
        'Consultation under GATT Articles XXII and XXIII',
        'Strengths and weaknesses of GATT dispute settlement',
        'Difference between GATT and WTO dispute settlement',
        'Dispute Settlement Body',
        'Panel establishment, composition and terms of reference',
        'Standard of review and burden of proof',
        'Appellate review and the Appellate Body crisis',
        'Adoption of reports',
        'Implementation and reasonable period of time',
        'Compensation, retaliation and compliance proceedings',
        'Special rules for developing countries',
    ]),
    M('Non-discrimination', [
        'Most-favoured-nation treatment under GATT Article I',
        'Meaning and scope of like products',
        'Advantages and systemic purpose of MFN treatment',
        'Customs unions and free-trade areas',
        'Generalized system of preferences',
        'Security, public-policy and trade-remedy exceptions to MFN',
        'National treatment under GATT Article III',
        'Internal taxes and internal regulation',
        'Directly competitive or substitutable products',
        'De jure and de facto discrimination',
        'Regional trade arrangements and non-discrimination',
    ]),
    M('Subsidies and countervailing measures', [
        'Financial contribution and benefit',
        'Specificity',
        'Prohibited subsidies',
        'Actionable subsidies',
        'Adverse effects, injury and serious prejudice',
        'Export and local-content subsidies',
        'WTO dispute remedies',
        'Domestic countervailing investigations',
        'Calculation of benefit and subsidy margin',
        'Causation and injury analysis',
        'Sunset and review of countervailing duties',
    ]),
    M('Dumping and anti-dumping measures', [
        'Export price and normal value',
        'Like product and fair comparison',
        'Dumping margin',
        'Domestic industry and standing',
        'Material injury and threat of injury',
        'Causal link and non-attribution',
        'Investigation procedure and disclosure',
        'Provisional measures, price undertakings and duties',
        'Lesser-duty rule',
        'Reviews and sunset',
        'Judicial and WTO review of anti-dumping action',
    ]),
    M('Trade in services, investment and intellectual property', [
        'Four modes of supply under GATS',
        'GATS MFN, transparency and domestic regulation',
        'Market-access and national-treatment commitments',
        'General and security exceptions under GATS',
        'Trade-Related Investment Measures',
        'Local-content and trade-balancing requirements',
        'TRIPS minimum standards and national treatment',
        'TRIPS most-favoured-nation treatment',
        'Enforcement and dispute settlement under TRIPS',
        'Public-health flexibilities and compulsory licensing',
    ]),
    M('International sale and export contracts', [
        'Structure of an international sale contract',
        'Choice of law and choice of forum',
        'Incoterms and allocation of cost and risk',
        'FOB contracts',
        'CIF contracts',
        'Quality, quantity, inspection and documentary compliance',
        'Force majeure and hardship',
        'Export controls, sanctions and compliance clauses',
        'Dispute-resolution clauses',
    ]),
    M('Payment in international trade', [
        'Open account and advance payment',
        'Documentary collection',
        'Letter of credit structure',
        'Applicant, issuing bank, advising bank and beneficiary',
        'Autonomy principle',
        'Strict compliance',
        'Fraud exception',
        'UCP rules and international standard banking practice',
        'Standby credits and guarantees',
        'Electronic presentation and trade finance risk',
    ]),
    M('Carriage of goods and transport documents', [
        'Contracts of carriage by sea',
        'Bills of lading as receipt, evidence and document of title',
        'Charterparties and liner carriage',
        'Carrier duties and seaworthiness',
        'Exceptions and limitation of liability',
        'Delivery against documents',
        'Containerized and multimodal transport',
        'Jurisdiction and arbitration clauses in transport documents',
        'Cargo claims and notice requirements',
    ]),
], edition='July 2020 archive', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/International-Trade-Law-2020.pdf',
   source_note='Best available official DU course material; several WTO institutional developments require a current-law check.',
   laws=['GATT 1994', 'WTO Agreement', 'Dispute Settlement Understanding', 'SCM Agreement', 'Anti-Dumping Agreement', 'GATS', 'TRIMS Agreement', 'TRIPS Agreement'],
   prereq=['@lb-205.m05','@lb-304.m04','@lb-303.m09'], elective=True, category='International economic law'),

S('LB-5035', 5, 'Rent Control and Slum Clearance', [
    M('Lease, licence and termination', [
        'Lease under the Transfer of Property Act',
        'Licence under the Easements Act',
        'Substance-over-form test for lease and licence',
        'Exclusive possession and control',
        'Contractual tenancy and statutory protection',
        'Tenancy by holding over',
        'Notice terminating a tenancy',
        'Effect of rent-control protection on termination notice',
    ]),
    M('Scope and key concepts of Delhi rent control', [
        'Object and policy of rent-control legislation',
        'Landlord, tenant and premises',
        'Premises excluded from the Delhi Rent Control Act',
        'Contractual and statutory tenants',
        'Heritability of residential tenancy',
        'Heritability of commercial tenancy',
        'Subtenant and lawful subletting',
        'Jurisdiction of the Rent Controller and civil court',
    ]),
    M('Standard rent and lawful charges', [
        'Purpose and concept of standard rent',
        'Fixation and calculation of standard rent',
        'Permitted increases',
        'Rent for improvements and additions',
        'Limitation for standard-rent applications',
        'Receipt for rent and deposit of rent',
        'Recovery of excess rent',
        'Amenities and essential supplies',
    ]),
    M('Eviction: default and misuse', [
        'Non-payment of rent',
        'Valid demand notice and tender',
        'Deposit orders and consequences of default',
        'First-default protection',
        'Subletting, assignment and parting with possession',
        'Change of user',
        'Nuisance and damage',
        'Breach of government lease conditions',
        'Unauthorized construction and misuse',
    ]),
    M('Eviction: landlord need and redevelopment', [
        'Bona fide requirement',
        'Ownership and landlord status',
        'Reasonable suitable alternative accommodation',
        'Requirement for dependent family members',
        'Limited tenancy and recovery',
        'Premises required for repairs or rebuilding',
        'Unsafe premises and redevelopment',
        'Re-entry and restoration where stated purpose is not used',
    ]),
    M('Summary procedure and rent-controller process', [
        'Eviction petition and jurisdictional facts',
        'Service of summons in summary proceedings',
        'Tenant affidavit seeking leave to defend',
        'Plausible defence and triable issue',
        'Consequences of refusing leave',
        'Evidence and interim rent orders',
        'Appeal, revision and supervisory jurisdiction',
        'Execution and use-and-occupation charges',
    ]),
    M('Slum areas: improvement and clearance', [
        'Declaration of slum area',
        'Improvement and clearance schemes',
        'Demolition and redevelopment powers',
        'Protection of occupants',
        'Prior permission for eviction proceedings',
        'Factors governing permission',
        'Interaction with rent-control eviction',
        'Rehousing, rehabilitation and constitutional concerns',
    ]),
    M('The 1995 Act and reform questions', [
        'Delhi Rent Act 1995 scheme',
        'Differences from the 1958 Act',
        'Rent-control objectives and market distortions',
        'Affordable housing and tenant security',
        'Model tenancy reforms',
        'Current applicability and commencement check',
    ]),
], edition='July 2020 archive', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/Rent-Control-2020.pdf',
   source_note='Archive material. Applicability, amendments and local notifications must be checked before use.',
   laws=['Delhi Rent Control Act, 1958', 'Slum Areas (Improvement and Clearance) Act, 1956', 'Delhi Rent Act, 1995', 'Transfer of Property Act, 1882', 'Indian Easements Act, 1882'],
   prereq=['@lb-204.m06','@lb-302.m16'], elective=True, category='Property and housing law'),

S('LB-5036', 5, 'Business Regulations', [
    M('Constitutional freedom of trade and business', [
        'Occupation, trade and business under Article 19(1)(g)',
        'Reasonable restrictions under Article 19(6)',
        'Professional and technical qualifications',
        'State monopoly',
        'Res extra commercium and harmful trades',
        'Freedom of trade, commerce and intercourse under Article 301',
        'Regulatory and compensatory measures',
        'Legislative competence over business regulation',
    ]),
    M('Securities and Exchange Board of India', [
        'Purpose and structure of SEBI',
        'Powers and functions of SEBI',
        'Registration and regulation of intermediaries',
        'Investor protection',
        'Inspection, investigation and directions',
        'Penalties and adjudication',
        'Securities Appellate Tribunal',
        'Appeal and judicial review',
        'Collective investment and public-issue regulation',
        'Strict and civil liability in securities regulation',
    ]),
    M('SARFAESI and enforcement of security interests', [
        'Secured creditor and secured asset',
        'Non-performing asset',
        'Demand notice',
        'Measures for enforcement without court intervention',
        'Possession, management and sale',
        'Borrower representation and reasons',
        'Remedy before the Debts Recovery Tribunal',
        'Appeal and pre-deposit',
        'Priority and interaction with insolvency law',
        'Constitutional validity and procedural fairness',
    ]),
    M('Takeover regulation', [
        'Substantial acquisition and control',
        'Trigger thresholds',
        'Persons acting in concert',
        'Open-offer obligation',
        'Offer price and timing',
        'Competing offers',
        'Exempt acquisitions',
        'Disclosure duties',
        'Withdrawal and completion',
        'SEBI enforcement and investor remedies',
    ]),
    M('Prevention of money laundering', [
        'Predicate or scheduled offence',
        'Proceeds of crime',
        'Money-laundering offence and process or activity',
        'Attachment of property',
        'Adjudication and confirmation',
        'Search, seizure, summons and arrest',
        'Burden and evidentiary presumptions',
        'Bail conditions',
        'Reporting-entity duties and beneficial ownership',
        'Special Court and confiscation',
        'Constitutional and due-process limits',
    ]),
    M('Essential commodities regulation', [
        'Purpose and scope of the Essential Commodities Act',
        'Declaration of essential commodities',
        'Control orders',
        'Production, supply, distribution and price control',
        'Search, seizure and confiscation',
        'Offences and company liability',
        'Delegated legislation and judicial review',
        'Market reform and amendment history',
    ]),
    M('Telecom regulation', [
        'Institutional structure of telecom regulation',
        'TRAI powers and functions',
        'Recommendations, regulations and tariff orders',
        'Licensing and spectrum interface',
        'Interconnection and access',
        'Consumer protection and quality of service',
        'TDSAT jurisdiction',
        'Competition and sectoral-regulator overlap',
    ]),
    M('Real-estate regulation', [
        'RERA objectives and institutional design',
        'Registration of projects and agents',
        'Promoter disclosures and duties',
        'Allottee rights and duties',
        'Separate-account and completion obligations',
        'Delay, refund, interest and compensation',
        'Real Estate Regulatory Authority',
        'Adjudicating officer and appellate tribunal',
        'Agreement for sale and unfair terms',
        'Interaction with consumer and insolvency remedies',
    ]),
    M('Insurance regulation', [
        'Purpose and structure of IRDAI',
        'Registration and control of insurers',
        'Regulation of intermediaries',
        'Solvency and prudential supervision',
        'Product and market-conduct oversight',
        'Policyholder protection',
        'Inspection, investigation and directions',
        'Penalties and appeals',
    ]),
], edition='July 2020 archive', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/Business-Regulations-July-2020.pdf',
   source_note='Archive compilation. Later amendments, replacement frameworks and current regulator instruments require verification.',
   laws=['Constitution of India', 'SEBI Act, 1992', 'SARFAESI Act, 2002', 'SEBI Takeover Regulations', 'Prevention of Money Laundering Act, 2002', 'Essential Commodities Act, 1955', 'TRAI Act, 1997', 'Real Estate (Regulation and Development) Act, 2016', 'IRDA Act, 1999'],
   prereq=['@lb-301.m07','@lb-303.m08','@lb-401.m03','@lb-402.m08'], elective=True, category='Regulatory and commercial law'),

S('LB-5037', 5, 'Intellectual Property Rights Law II', [
    M('Copyright subject matter and originality', [
        'Nature, purpose and scope of copyright',
        'Copyright as a statutory right',
        'Idea-expression dichotomy',
        'Concept of a work',
        'Literary works',
        'Dramatic and musical works',
        'Artistic works',
        'Cinematograph films and sound recordings',
        'Computer programs and databases',
        'Originality: labour, skill and judgment',
        'Sweat-of-the-brow and minimal-creativity standards',
        'Works in which copyright subsists',
    ]),
    M('Exclusive and moral rights', [
        'Reproduction right',
        'Distribution and issue of copies',
        'Public performance and communication to the public',
        'Making films and sound recordings',
        'Translation and adaptation',
        'Commercial rental right',
        'Rights across different classes of works',
        'Term of protection',
        'Author’s moral rights',
        'Performer’s moral rights',
    ]),
    M('Authorship, ownership and exploitation', [
        'Concept of author',
        'First ownership',
        'Employment and commissioned works',
        'Joint authorship',
        'Producer and production roles',
        'Artificial intelligence and human authorship',
        'Assignment',
        'Voluntary licences',
        'Compulsory licences',
        'Statutory licences',
        'Relinquishment',
        'Copyright societies and collective management',
    ]),
    M('Copyright infringement, exceptions and remedies', [
        'Primary infringement',
        'Substantial copying and similarity',
        'Authorizing and secondary infringement',
        'Fair dealing',
        'Education and research exceptions',
        'Library, archive and accessibility exceptions',
        'Public events and religious-ceremony exceptions',
        'Technological protection measures',
        'Rights-management information',
        'Civil remedies',
        'Criminal offences',
        'Intermediary and digital-platform issues',
    ]),
    M('Related rights', [
        'Broadcast reproduction right',
        'Meaning of broadcast',
        'Performer and performance',
        'Performer’s economic rights',
        'Moral rights of performers',
        'Exceptions to related rights',
        'Relationship between underlying works and recordings',
    ]),
    M('Patent system and patentability', [
        'Objects and theories of patent protection',
        'Patents Act structure and TRIPS influence',
        'Meaning of invention',
        'Novelty',
        'Inventive step and non-obviousness',
        'Industrial applicability',
        'Patentable subject matter',
        'Non-patentable inventions',
        'Section 3(d) and incremental pharmaceutical inventions',
        'Disclosure, enablement and claim scope',
    ]),
    M('Patent application, examination and opposition', [
        'Provisional and complete specifications',
        'Claims and claim construction',
        'Ordinary, convention and PCT applications',
        'Publication and request for examination',
        'Examination and response to objections',
        'Pre-grant opposition',
        'Post-grant opposition',
        'Grounds of opposition and revocation',
        'Priority and anticipation',
        'Controller’s powers and procedural fairness',
    ]),
    M('Patent licensing and public interest', [
        'Voluntary licensing',
        'Compulsory licences',
        'Public-health grounds',
        'Export of pharmaceuticals under compulsory licence',
        'Parallel import',
        'Bolar or regulatory-review exception',
        'Government use and acquisition',
        'Standard-essential patents',
        'FRAND commitments and injunctions',
        'Competition-law limits on patent exploitation',
    ]),
    M('Patent rights and infringement', [
        'Rights of a patentee',
        'Product and process infringement',
        'Literal and purposive claim construction',
        'Doctrine of equivalents',
        'Jurisdiction and interim injunctions',
        'Validity challenge as a defence',
        'Gillette defence',
        'Experimental and statutory exceptions',
        'Damages, account of profits and delivery up',
    ]),
    M('Plant varieties and farmers’ rights', [
        'Objectives and structure of plant-variety protection',
        'Breeder, farmer and community',
        'New, extant, farmers’ and essentially derived varieties',
        'Distinctiveness, uniformity and stability',
        'Registration and denomination',
        'Breeders’ rights',
        'Farmers’ rights and seed saving',
        'Researchers’ rights',
        'Benefit sharing and community claims',
        'UPOV models and the Indian approach',
    ]),
    M('Trade secrets', [
        'Meaning and subject matter of trade secrets',
        'Secrecy, commercial value and reasonable steps',
        'Contract, confidence and equitable protection',
        'Employee and commercial relationships',
        'Licensing and confidentiality clauses',
        'Misappropriation and lawful reverse engineering',
        'Civil remedies and evidence preservation',
        'International framework under TRIPS',
    ]),
    M('Traditional knowledge and folklore', [
        'Meaning and forms of traditional knowledge',
        'Traditional cultural expressions and folklore',
        'Defensive and positive protection',
        'Prior-art databases',
        'Biopiracy and misappropriation',
        'Community ownership and benefit sharing',
        'Interface with biodiversity law',
        'WIPO negotiations and unresolved policy choices',
    ]),
], edition='July 2020 archive', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/IPR-II-July-2020.pdf',
   source_note='Best available official DU material. Current amendments, rules and digital/AI developments must be checked.',
   laws=['Copyright Act, 1957', 'Patents Act, 1970', 'Protection of Plant Varieties and Farmers’ Rights Act, 2001', 'TRIPS Agreement'],
   prereq=['@lb-4036.m05','@lb-303.m03'], elective=True, category='Intellectual property law'),

S('LB-504', 5, 'Principles of Taxation Law', [
    M('Income-tax structure and core concepts', [
        'Tax, cess and surcharge',
        'Direct and indirect taxes',
        'Constitutional allocation of taxing power',
        'General scheme of the Income-tax Act 1961',
        'Definition and inclusiveness of income',
        'Capital receipt and revenue receipt',
        'Application of income and diversion by overriding title',
        'Assessee',
        'Previous year and assessment year',
        'Receipt, accrual and deemed accrual',
        'Basis and charging provisions',
    ]),
    M('Agricultural income', [
        'Meaning of agricultural income',
        'Rent or revenue from agricultural land',
        'Agricultural operations',
        'Basic and subsequent operations',
        'Income from farm buildings',
        'Processing and marketability',
        'Composite agricultural and business income',
        'Exemption and rate integration',
    ]),
    M('Residence and scope of total income', [
        'Residential status of an individual',
        'Resident and ordinarily resident',
        'Resident but not ordinarily resident',
        'Non-resident',
        'Residence of firms and companies',
        'Scope of total income by residential status',
        'Income received or deemed received in India',
        'Income accruing or deemed to accrue in India',
        'Business connection and significant economic presence',
        'Source rules and cross-border income',
    ]),
    M('Income from salaries', [
        'Employer-employee relationship',
        'Charge and timing of salary income',
        'Basic salary, allowances and perquisites',
        'Profits in lieu of salary',
        'Retirement receipts',
        'Exemptions and deductions',
        'Valuation of perquisites',
    ]),
    M('Income from house property', [
        'Ownership and charge',
        'Annual value',
        'Self-occupied and let-out property',
        'Expected and actual rent',
        'Vacancy and unrealized rent',
        'Municipal taxes',
        'Standard deduction and interest',
        'Deemed ownership and co-ownership',
    ]),
    M('Business and professional income', [
        'Scope of profits and gains of business or profession',
        'Method of accounting',
        'Allowable business expenditure',
        'Capital and revenue expenditure',
        'Personal and prohibited expenditure',
        'Depreciation and block of assets',
        'Bad debts and provisions',
        'Stock valuation',
        'Presumptive taxation overview',
        'Business deductions and disallowances',
    ]),
    M('Capital gains', [
        'Capital asset and transfer',
        'Short-term and long-term assets',
        'Full value of consideration',
        'Cost of acquisition and improvement',
        'Indexation',
        'Deemed transfers and deemed consideration',
        'Exempt rollover investments',
        'Transactions not regarded as transfer',
        'Computation and loss treatment',
    ]),
    M('Income from other sources', [
        'Residual charging provision',
        'Dividends and interest',
        'Gifts and receipts without consideration',
        'Family pension',
        'Winnings and special-rate income',
        'Deductions',
        'Deemed income and unexplained credits overview',
    ]),
    M('Clubbing of income', [
        'Transfer of income without transfer of asset',
        'Revocable transfer',
        'Income of spouse',
        'Transfer of assets to spouse or son’s wife',
        'Income of minor child',
        'Conversion of individual property into family property',
        'Tracing, indirect transfer and exceptions',
    ]),
    M('Assessment and reassessment', [
        'Return of income and self-assessment',
        'Processing and scrutiny assessment',
        'Best-judgment assessment',
        'Failure to comply and estimation',
        'Income escaping assessment',
        'Information suggesting escapement',
        'Notice, hearing and limitation',
        'Assessment orders and reasons',
        'Appeal, rectification and revision overview',
        'Burden, penalty and prosecution interface',
    ]),
], edition='January 2023; PDF labels paper LB-604', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/VIth%20Term_Principles%20of%20Taxation%20Law_LB%20604_2023.pdf',
   source_note='The DU catalog lists this as Term V LB-504, while the linked PDF labels it VI Term LB-604. The stable node follows the catalog title/code and records the PDF alias.',
   aliases=['LB-604 (PDF label)', 'Principles of Taxation Laws'], catalog_code='LB-504',
   laws=['Constitution of India', 'Income-tax Act, 1961', 'Income-tax Rules, 1962'],
   prereq=['@lb-301.m06','@lb-303.m07','@lb-201.m06'], category='Tax law'),
]

# Term VI ---------------------------------------------------------------------
SUBJECTS += [
S('LB-601', 6, 'Advocacy, Professional Ethics and Accountancy for Lawyers', [
    M('Legal profession and the Advocates Act', [
        'History and development of the legal profession in India',
        'Advocates Act 1961 structure',
        'State Bar Councils',
        'Bar Council of India',
        'Bar Council committees and functions',
        'Enrollment and state rolls',
        'Senior advocates and other advocates',
        'Right to practise and its limits',
        'Reciprocity and foreign lawyers',
        'Legal education and professional regulation',
    ]),
    M('Qualities and craft of advocacy', [
        'Seven lamps of advocacy',
        'Honesty and candour',
        'Courage and independence',
        'Industry and preparation',
        'Wit, tact and judgment',
        'Fellowship and professional civility',
        'Command of facts and record',
        'Case theory and theme',
        'Examination and cross-examination overview',
        'Written and oral submissions',
    ]),
    M('Contempt of court', [
        'Purpose and constitutional basis of contempt power',
        'Civil contempt',
        'Criminal contempt',
        'Scandalising the court',
        'Prejudice to judicial proceedings',
        'Interference with administration of justice',
        'Fair and accurate reporting',
        'Fair criticism and truth as a defence',
        'Intent, knowledge and substantial interference',
        'Procedure, notice and punishment',
        'Apology and proportionality',
        'Contempt by advocates, judges, companies and public officials',
    ]),
    M('Disciplinary control and professional misconduct', [
        'Meaning and range of professional misconduct',
        'Complaint to a State Bar Council',
        'Disciplinary committee procedure',
        'Reprimand, suspension and removal',
        'Appeal to the Bar Council of India',
        'Appeal to the Supreme Court',
        'Court power concerning advocate misconduct',
        'Natural justice in disciplinary proceedings',
        'Strikes, boycotts and abandonment of client',
        'Retention of files and lien claims',
    ]),
    M('Duties to court and administration of justice', [
        'Candour and prohibition on misleading the court',
        'Respectful independence',
        'No private communication with a judge',
        'No influence by improper means',
        'Duty concerning false evidence and fraud',
        'Proper dress and decorum',
        'Avoiding appearance before related decision-makers',
        'Duty to accept briefs and permissible refusal',
        'No strike or obstruction of court work',
        'Duty to uphold rule of law and legal aid',
    ]),
    M('Duties to clients', [
        'Competence, diligence and communication',
        'Confidentiality and legal professional privilege',
        'Conflict of interest',
        'Acting on client instructions within law',
        'Full and frank fee disclosure',
        'No contingency fee or trafficking in litigation',
        'Client money and property',
        'Withdrawal and reasonable notice',
        'No purchase of subject matter in litigation',
        'Return of files and unearned money',
    ]),
    M('Duties to opponents, colleagues and the profession', [
        'Fair dealing with opponents',
        'Communication with represented parties',
        'Honouring legitimate professional undertakings',
        'No solicitation or advertising beyond permitted limits',
        'Restrictions on other employment',
        'Training and supervision of juniors',
        'Professional courtesy and non-discrimination',
        'Duty to render legal aid',
        'Bench-bar relationship',
        'Law teaching and compatible occupations',
    ]),
    M('Office management and lawyer accountancy', [
        'Purpose and branches of accounting',
        'Cash and accrual concepts',
        'Books of account and source documents',
        'Client ledger and office ledger',
        'Trust or client money segregation',
        'Receipts, payments and reconciliation',
        'Fees, retainers and expenses',
        'Income-and-expenditure or profit-and-loss statement',
        'Balance sheet and basic interpretation',
        'Assets, liabilities, capital and cash flow',
        'Reading financial statements in litigation',
        'Time, human-resource and file management',
        'Audit trail, retention and confidentiality',
    ]),
], edition='January 2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/VIth%20Term_Advocacy%20Professional%20Ethics%20and%20Accountancy%20for%20Lawyers_LB%20601_2023.pdf',
   laws=['Advocates Act, 1961', 'Bar Council of India Rules', 'Contempt of Courts Act, 1971', 'Constitution of India'],
   prereq=['f25','@lb-501.m09','@lb-502.m10'], category='Professional skills and ethics'),

S('LB-602', 6, 'Alternative Dispute Resolution', [
    M('ADR system and process choice', [
        'Need for alternatives to formal adjudication',
        'Rights-based and interest-based processes',
        'Litigation, arbitration, mediation, conciliation and negotiation compared',
        'Binding and non-binding processes',
        'Party autonomy and procedural fairness',
        'Confidentiality and without-prejudice communication',
        'Suitability screening and power imbalance',
        'Court referral to ADR',
        'Online dispute resolution',
        'Enforceability of outcomes',
    ]),
    M('Communication for dispute resolution', [
        'Active listening',
        'Open, closed and clarifying questions',
        'Reframing and summarizing',
        'Verbal communication',
        'Non-verbal communication and body language',
        'Paralanguage and tone',
        'One-way and two-way communication',
        'Empathy without loss of neutrality',
        'Managing difficult conversations',
        'Communication simulation and feedback',
    ]),
    M('Negotiation', [
        'Positions, interests and needs',
        'Distributive and integrative negotiation',
        'Negotiation styles',
        'BATNA, WATNA and reservation point',
        'Objective criteria',
        'Option generation and package deals',
        'Anchoring and concessions',
        'Assertiveness and relationship management',
        'Common negotiation errors',
        'Seven-element framework',
        'Ethics, authority and confidentiality',
        'Recording and enforcing a negotiated settlement',
    ]),
    M('Mediation and conciliation', [
        'Difference between mediation, conciliation and adjudication',
        'Mediator role and neutrality',
        'Opening statement',
        'Party opening statements',
        'Joint session',
        'Agenda setting and issue identification',
        'Private caucus and confidentiality',
        'Reality testing',
        'Managing emotion, silence and apology',
        'Breaking impasse',
        'Final negotiation and closure',
        'Drafting a mediation settlement',
        'Ethical dilemmas and conflicts',
        'Singapore Convention and cross-border settlement',
        'Mediation Act and current framework check',
    ]),
    M('Arbitration: agreement and tribunal', [
        'Arbitration agreement and separability',
        'Domestic and international commercial arbitration',
        'Seat, venue and curial law',
        'Court referral and stay of litigation',
        'Appointment and composition of tribunal',
        'Independence, impartiality and disclosure',
        'Challenge and termination of mandate',
        'Competence-competence',
        'Interim measures by court and tribunal',
        'Drafting a workable arbitration clause',
    ]),
    M('Arbitral procedure and award', [
        'Party autonomy and equal treatment',
        'Pleadings, evidence and hearings',
        'Applicable substantive law',
        'Time limits and fast-track procedure',
        'Settlement during arbitration',
        'Form, reasons and correction of award',
        'Costs and interest',
        'Setting aside an award',
        'Enforcement of domestic awards',
        'Foreign awards and New York Convention',
        'Public policy and patent illegality',
    ]),
    M('Legal services, Lok Adalat and field learning', [
        'Constitutional basis of legal aid',
        'Legal Services Authorities Act structure',
        'National, State, District and Taluk authorities',
        'Lok Adalat jurisdiction and process',
        'Nature and effect of Lok Adalat award',
        'Permanent Lok Adalat and public utility services',
        'Pre-litigation settlement',
        'Mediation centres and institutional ADR',
        'Court-annexed ADR observation',
        'Field-visit ethics, observation and report writing',
    ]),
], edition='January 2023 archive', source='https://lawfaculty.du.ac.in/old-lawfaculty/files/LLB/LLBCM23/VIth%20Term_ADR%20Course-LB%20602_2023.pdf',
   source_note='Official DU archive; the source predates parts of the present mediation framework, so current legislation and rules must be checked.',
   laws=['Arbitration and Conciliation Act, 1996', 'Mediation Act, 2023', 'Legal Services Authorities Act, 1987', 'Code of Civil Procedure, 1908'],
   prereq=['f22','@lb-302.m18','@lb-501.m08','@lb-502.m09'], category='Dispute resolution and professional skills'),

S('LB-603', 6, 'Environmental Law', [
    M('International environmental law', [
        'Development and sources of international environmental law',
        'Stockholm Conference and Declaration 1972',
        'UNEP and international environmental institutions',
        'World Charter for Nature',
        'Ozone protection and Montreal Protocol',
        'Hazardous chemicals and Rotterdam Convention',
        'Transboundary waste and Basel Convention',
        'Persistent organic pollutants and Stockholm Convention',
        'Rio Declaration and Agenda 21',
        'Convention on Biological Diversity',
        'Cartagena Protocol on Biosafety',
        'UNFCCC, Kyoto Protocol and Paris Agreement',
        'Aarhus procedural environmental rights',
        'Sustainable Development Goals',
        'No-harm rule and transboundary environmental impact',
    ]),
    M('Fundamental environmental principles', [
        'Development versus environment',
        'Sustainable development',
        'Inter-generational equity',
        'Intra-generational equity',
        'Precautionary principle',
        'Polluter-pays principle',
        'Public-trust doctrine',
        'Prevention principle',
        'Common but differentiated responsibilities',
        'Community and indigenous rights',
        'Environmental rule of law',
    ]),
    M('Constitutional environmental protection', [
        'Equality and non-arbitrariness in environmental decisions',
        'Trade freedom and environmental restriction',
        'Right to life, livelihood and a wholesome environment',
        'Directive principles on health and environment',
        'Fundamental duty to protect nature',
        'Supreme Court and High Court writ powers',
        'Environmental public-interest litigation',
        'Relaxed standing and representative standing',
        'Continuing mandamus',
        'Collaborative and investigative adjudication',
        'Separation of powers and expert decision-making',
    ]),
    M('Water, air and noise pollution control', [
        'Meaning and sources of water pollution',
        'Central and State Pollution Control Boards',
        'Pollution-control areas and standards',
        'Consent to establish and operate',
        'Sampling and evidentiary procedure',
        'Directions, restraint and closure',
        'Citizen complaints and prosecution',
        'Meaning and sources of air pollution',
        'Air-pollution control areas',
        'Vehicular pollution',
        'Noise Pollution Rules',
        'Offences, penalties and company liability',
    ]),
    M('Environment Protection Act and impact assessment', [
        'Purpose and scope of the Environment Protection Act',
        'Environment, pollutant and hazardous substance',
        'Central Government powers and delegation',
        'Standards, directions and closure powers',
        'Environmental Impact Assessment notification',
        'Screening, scoping, appraisal and public consultation',
        'Environmental clearance and conditions',
        'Ex post facto clearance controversy',
        'Environmental audit and compliance monitoring',
        'Hazardous activities and absolute liability',
        'Industrial disaster and compensation',
        'Climate and energy-law gaps',
    ]),
    M('National Green Tribunal', [
        'Purpose and composition of the NGT',
        'Original and appellate jurisdiction',
        'Schedule I enactments',
        'Limitation',
        'Standing and access to the Tribunal',
        'Relief, compensation and restitution',
        'Application of environmental principles',
        'Procedure, evidence and expert role',
        'Suo motu environmental jurisdiction',
        'Appeal to the Supreme Court',
        'Compliance and enforcement of NGT orders',
    ]),
    M('Forests, biodiversity and wildlife', [
        'Reserved, protected, village and private forests',
        'Forest diversion and central approval',
        'Meaning of forest and conservation jurisdiction',
        'Rights of Scheduled Tribes and other forest dwellers',
        'Individual and community forest rights',
        'Biological resources and associated knowledge',
        'Access and benefit sharing',
        'National and State biodiversity institutions',
        'Genetically modified organisms and biosafety',
        'Wildlife protection framework',
        'Protected species and trade',
        'Sanctuaries, national parks and conservation reserves',
        'Zoos, captive animals and human-wildlife conflict',
    ]),
], edition='January 2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/VIth%20Term_Environmental%20Law_LB-603_2023.pdf',
   laws=['Environment (Protection) Act, 1986', 'Water Act, 1974', 'Air Act, 1981', 'National Green Tribunal Act, 2010', 'Wild Life (Protection) Act, 1972', 'Forest (Conservation) Act, 1980', 'Biological Diversity Act, 2002', 'Forest Rights Act, 2006'],
   prereq=['@lb-401.m03','@lb-402.m08','@lb-205.m07','@lb-103.m08'], category='Environmental and public law'),

S('LB-604', 6, 'Jurisprudence II', [
    M('Dharma and rule of law', [
        'Concept and sources of dharma',
        'Trivarga theory',
        'Achara, vyavahara and prayaschitta',
        'Rule of law',
        'Rule of dharma',
        'Satyameva Jayate and Yato Dharmastato Jayah',
        'Spirituality, morality and legal order',
        'Comparing civilizational accounts of lawful government',
    ]),
    M('Rights and duties', [
        'Duty-centred accounts in Dharmasutra thought',
        'Hohfeldian jural relations',
        'Claim-right and duty',
        'Liberty and no-right',
        'Power and liability',
        'Immunity and disability',
        'Limits and critiques of Hohfeld’s scheme',
        'Laches and constitutional remedies',
        'Modern rights and Marxist critique',
        'Balancing rights, duties and collective claims',
    ]),
    M('Person and legal personality', [
        'Natural and juristic persons',
        'Theories of corporate personality',
        'Legal status of deities and religious institutions',
        'Rights of animals',
        'Interests of unborn and future generations',
        'River and nature personhood',
        'Representation and guardianship of non-human entities',
        'Instrumental and moral limits of legal personality',
    ]),
    M('Possession and ownership', [
        'Corpus and animus in possession',
        'Possession in fact and possession in law',
        'Immediate and mediate possession',
        'Acquisition and loss of possession',
        'Possessory remedies and relativity of title',
        'Incidents of ownership',
        'Ownership as a bundle of rights',
        'Sole, co-, trust and limited ownership',
        'Ancient Indian accounts of agricultural-land ownership',
        'Possession, title and social function',
    ]),
    M('Theories of justice', [
        'Kautilya on administration of justice',
        'Fuller and substantive or procedural natural law',
        'Rawls: original position and principles of justice',
        'Rawls: fair equality and difference principle',
        'Nozick: entitlement theory',
        'Corrective and distributive justice',
        'Amartya Sen: niti and nyaya',
        'Capability, comparison and removal of manifest injustice',
        'Fairness, impartiality and equitable distribution',
    ]),
    M('Indian logic, epistemology and interpretation', [
        'Nyaya as a system of logic and inquiry',
        'Sixteen categories of Nyaya',
        'Pramana and sources of valid knowledge',
        'Inference, analogy and testimony',
        'Nyaya methods of dialectic',
        'Fallacies and defeat conditions',
        'Mimamsa science of interpretation',
        'Text, sentence, context and purpose in Mimamsa',
        'Buddhist logic and epistemology',
        'Use of Indian logical traditions in legal reasoning',
    ]),
], edition='January 2026', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/Jurisprudence26thSemester2026.pdf',
   aliases=['Jurisprudence-II'], laws=['Constitution of India'],
   prereq=['@lb-106.m07','@lb-401.m11','@lb-204.m12'], category='Legal theory'),

S('LB-6031', 6, 'Interpretation of Statutes', [
    M('Meaning and need for interpretation', [
        'Meaning of interpretation and construction',
        'Why statutory language becomes uncertain',
        'Text, context, purpose and institutional role',
        'Commencement, repeal and amendment',
        'Prospective and retrospective operation',
        'Mandatory and directory provisions',
        'Consolidating, codifying and declaratory statutes',
        'Interpretation and separation of powers',
    ]),
    M('Theories and primary rules', [
        'Literal or ordinary-meaning rule',
        'Golden rule',
        'Mischief rule',
        'Purposive interpretation',
        'Harmonious construction',
        'Reading provisions as a whole',
        'Beneficial and remedial construction',
        'Strict construction of penal and taxing statutes',
        'Constitutional interpretation and transformative purpose',
    ]),
    M('Linguistic canons and presumptions', [
        'Ejusdem generis',
        'Noscitur a sociis',
        'Expressio unius',
        'Generalia specialibus non derogant',
        'Ut res magis valeat quam pereat',
        'Reddendo singula singulis',
        'Presumption against redundancy',
        'Presumption against absurdity',
        'Presumption against ouster of jurisdiction',
        'Presumption against retrospectivity',
    ]),
    M('Internal aids', [
        'Long and short titles',
        'Preamble',
        'Headings and marginal notes',
        'Definitions',
        'Provisos',
        'Explanations and illustrations',
        'Exceptions and saving clauses',
        'Schedules',
        'Punctuation',
        'Non-obstante clauses',
    ]),
    M('External aids', [
        'Historical setting and prior law',
        'Statement of objects and reasons',
        'Legislative debates',
        'Committee and Law Commission reports',
        'Dictionaries and technical works',
        'International conventions',
        'Administrative construction and contemporanea expositio',
        'Foreign decisions and comparative law',
        'Subsequent legislation and amendments',
    ]),
    M('Plain language and contemporary interpretation', [
        'Plain-language drafting and accessibility',
        'Dynamic and updating construction',
        'Reading down',
        'Severability',
        'Constitutional avoidance',
        'Casus omissus and limits on supplying omissions',
        'Digital texts and machine-readable legislation',
        'Multilingual enactments and authoritative text',
        'Use and limits of corpus linguistics and technology',
    ]),
], edition='January 2023 archive', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/VIth%20Term_Interpretation%20of%20Statutes_LB-%206031_2023.pdf',
   source_note='Older elective overlapping with the newer compulsory LB-404 course structure; kept as a distinct catalog node and cross-linked.',
   laws=['General Clauses Act, 1897', 'Constitution of India'], prereq=['@lb-404.m05'], related=['@lb-404'], elective=True, category='Legal method and legislation'),

S('LB-6032', 6, 'Insurance and Banking Law', [
    M('Contract of insurance', [
        'Risk transfer and mitigation',
        'Insurance and indemnity',
        'Premium',
        'Life insurance',
        'Fire insurance',
        'Marine insurance',
        'Formation of an insurance contract',
        'Performance and discharge',
        'Insurer, insured, beneficiary and nominee',
        'Regulatory overlay on contract terms',
    ]),
    M('Special principles of insurance', [
        'Utmost good faith',
        'Disclosure and misrepresentation',
        'Insurable interest',
        'Proximate cause',
        'Subrogation',
        'Contribution',
        'Indemnity and valued policies',
        'Mitigation of loss',
        'Contract of adhesion',
        'Fundamental breach and warranties',
    ]),
    M('Construction and claims', [
        'Reading the policy as a whole',
        'Proposal, schedule, conditions and endorsements',
        'Coverage clause and exclusion',
        'Contra proferentem',
        'Causal connection and exclusions',
        'Claims notice and cooperation',
        'Repudiation and reasons',
        'Consumer remedies and unfair terms',
        'Surveyors and loss assessment',
        'Damages, interest and costs',
    ]),
    M('Evolution and banker-customer relationship', [
        'History of banking in India',
        'Bank nationalization and social control',
        'Types of banks and their functions',
        'Banker and customer',
        'Debtor-creditor relationship',
        'Mandate, confidentiality and duty of care',
        'Payment, collection and wrongful dishonour',
        'Banker’s lien, set-off and appropriation',
        'Banking-sector reform committees',
        'Digital banking and payment-system interface',
    ]),
    M('Banking regulation and Reserve Bank control', [
        'Bank, banking and banking company',
        'Licensing of banks',
        'Permitted and restricted business',
        'Management and governance controls',
        'Inspection, directions and supervisory powers',
        'Capital, reserve and prudential requirements',
        'Non-performing assets',
        'Amalgamation, moratorium and winding up',
        'RBI incorporation and central-banking functions',
        'Monetary and credit policy',
        'Credit information',
        'Non-banking financial companies',
    ]),
    M('Integrated Ombudsman Scheme', [
        'Purpose and coverage of the scheme',
        'Grounds of complaint',
        'Preconditions and limitation',
        'Filing and digital complaint process',
        'Role and powers of the Ombudsman',
        'Facilitation, settlement and award',
        'Compensation',
        'Appeal and review',
        'Interaction with consumer and court remedies',
    ]),
    M('Negotiable instruments', [
        'Negotiability and statutory instruments',
        'Promissory note',
        'Bill of exchange',
        'Cheque and electronic cheque',
        'Drawer, drawee, acceptor, payee and endorser',
        'Holder and holder in due course',
        'Negotiation and endorsement',
        'Presentment and payment',
        'Material alteration',
        'Crossing of cheques',
        'Collecting and paying banker protection',
    ]),
    M('Dishonour of cheques', [
        'Ingredients of the statutory offence',
        'Legally enforceable debt or liability',
        'Presentation within validity period',
        'Return unpaid for covered reasons',
        'Demand notice',
        'Failure to pay within statutory period',
        'Cause of action and limitation',
        'Territorial jurisdiction',
        'Presumptions and rebuttal',
        'Company and vicarious liability',
        'Interim compensation and appellate deposit',
        'Compounding and summary trial',
    ]),
], edition='January 2025', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/Ins%20and%20Banking%20case%20mat-%202025%20%284%29.pdf%20NEW.pdf',
   laws=['Insurance Act, 1938', 'Marine Insurance Act, 1963', 'IRDA Act, 1999', 'Banking Regulation Act, 1949', 'Reserve Bank of India Act, 1934', 'Negotiable Instruments Act, 1881'],
   prereq=['@lb-102.m11','@lb-304.m07','@lb-303.m08','@lb-201.m06'], elective=True, category='Financial and commercial law'),

S('LB-6033', 6, 'Election Laws', [
    M('Constitutional and institutional framework', [
        'Representative democracy and electoral legitimacy',
        'Constitutional provisions on elections',
        'Election Commission of India',
        'Superintendence, direction and control',
        'Independence and appointment of election commissioners',
        'Delimitation and reservation of constituencies',
        'Electoral rolls and adult suffrage',
        'Model Code of Conduct',
        'Judicial review during the election process',
    ]),
    M('Political parties and candidates', [
        'Registration and recognition of political parties',
        'Reserved symbols',
        'Inner-party democracy and transparency',
        'Candidate qualification',
        'Nomination papers',
        'Deposits and proposers',
        'Candidate affidavits and disclosure',
        'Criminal antecedents, assets and education',
        'Right to know and voter information',
    ]),
    M('Election process and voting', [
        'Election notification and calendar',
        'Scrutiny of nominations',
        'Withdrawal and uncontested return',
        'Campaign regulation',
        'Polling agents and polling stations',
        'Secret ballot',
        'Electronic voting machines and VVPAT',
        'Postal and proxy voting',
        'Counting, recount and declaration of result',
        'NOTA and voter choice',
    ]),
    M('Disqualifications', [
        'Constitutional disqualifications',
        'Office of profit',
        'Government contracts and pecuniary interests',
        'Dismissal for corruption or disloyalty',
        'Failure to lodge election expenses',
        'Disqualification on conviction',
        'Duration and removal of disqualification',
        'Sitting members and immediate effect of conviction',
        'Pending criminal cases and reform proposals',
    ]),
    M('Anti-defection law', [
        'Purpose and history of the Tenth Schedule',
        'Voluntarily giving up party membership',
        'Voting or abstaining contrary to whip',
        'Independent and nominated members',
        'Merger exception',
        'Speaker or Chairperson as decision-maker',
        'Judicial review',
        'Timing, delay and interim consequences',
        'Ninety-first Amendment and ministerial office',
        'Critiques and reform options',
    ]),
    M('Election petitions and invalid elections', [
        'Exclusive statutory remedy and election petition',
        'Standing, parties, limitation and security',
        'Pleadings and material facts',
        'Trial and burden of proof',
        'Improper acceptance or rejection of nomination',
        'Improper reception, refusal or rejection of votes',
        'Non-compliance with Constitution or election law',
        'Material effect on result',
        'Void election and declaration of another candidate',
        'Appeal and finality',
    ]),
    M('Corrupt practices and electoral offences', [
        'Difference between corrupt practice and electoral offence',
        'Bribery',
        'Undue influence',
        'Appeal on religion, race, caste, community or language',
        'Promotion of enmity and hatred',
        'False statements about personal character',
        'Hiring or procuring vehicles',
        'Excess election expenditure',
        'Government-servant assistance',
        'Booth capturing and intimidation',
        'Proof, agency and consent',
        'Consequences and disqualification',
    ]),
    M('Campaign finance, media and reform', [
        'Candidate election expenses',
        'Party finance and contribution disclosure',
        'Electoral bonds and constitutional scrutiny',
        'Paid news and political advertising',
        'Broadcast and social-media campaigning',
        'Silence period and exit polls',
        'Misinformation and deepfakes',
        'State resources and level playing field',
        'Simultaneous elections debate',
        'Electoral reform institutions and reports',
    ]),
], edition='January 2025', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/LB-6033%20Election%20Laws%202025.pdf',
   laws=['Constitution of India', 'Representation of the People Act, 1950', 'Representation of the People Act, 1951', 'Election Symbols Order, 1968', 'Conduct of Elections Rules, 1961'],
   prereq=['@lb-301.m07','@lb-401.m09','@lb-201.m06','@lb-203.m10'], elective=True, category='Constitutional and electoral law'),

S('LB-6034', 6, 'Minor Acts and Supreme Court Rules', [
    M('Registration Act: documents and duty to register', [
        'Purpose and territorial organization of registration law',
        'Compulsorily registrable documents',
        'Optional registration',
        'Lease, gift, sale and other non-testamentary instruments',
        'Family arrangements and memoranda',
        'Awards, decrees and court orders',
        'Documents containing rights in immovable property',
        'Exemptions and special categories',
    ]),
    M('Registration procedure and legal effect', [
        'Proper registration office',
        'Time for presentation and delay',
        'Persons entitled to present',
        'Admission and denial of execution',
        'Enquiry by registering officer',
        'Refusal, appeal and civil suit',
        'Effective date of a registered document',
        'Effect of non-registration',
        'Collateral-purpose use',
        'Priority and notice',
        'Electronic and current procedural check',
    ]),
    M('Indian Stamp Act', [
        'Purpose and nature of stamp duty',
        'Instrument and chargeability',
        'Execution and timing of stamping',
        'Valuation and consideration',
        'Several instruments in one transaction',
        'Conveyance, lease, mortgage, partition and award',
        'Impounding an insufficiently stamped instrument',
        'Admissibility and curing deficiency',
        'Penalty and prosecution',
        'Reference to revenue authority',
        'State amendments and applicable schedule check',
    ]),
    M('Court fees and suit valuation', [
        'Purpose of court fees',
        'Ad valorem and fixed fees',
        'Valuation from relief claimed',
        'Declaratory and consequential relief',
        'Possession, partition and cancellation suits',
        'Accounts and administration suits',
        'Deficiency and opportunity to cure',
        'Rejection of plaint for deficient fee',
        'Suits Valuation Act and jurisdictional value',
        'Plaintiff valuation and court scrutiny',
        'State amendments and current schedules',
    ]),
    M('Supreme Court jurisdiction and access', [
        'Constitutional basis for Supreme Court rules',
        'Original jurisdiction',
        'Civil and criminal appellate jurisdiction',
        'Special leave petitions',
        'Review petitions',
        'Curative petitions',
        'Writ and public-interest proceedings',
        'Transfer petitions',
        'Contempt proceedings',
        'Party-in-person and legal-aid access',
    ]),
    M('Supreme Court filing and case management', [
        'Advocate-on-Record system',
        'Vakalatnama and authorization',
        'Petition format, synopsis and list of dates',
        'Affidavit, annexures and certified copies',
        'Limitation and application for condonation',
        'Filing, scrutiny, defects and re-filing',
        'Service, appearance and counter affidavit',
        'Interlocutory applications',
        'Listing, mentioning and circulation',
        'Paper books and record',
        'Costs, decree and enforcement',
        'E-filing and current practice directions',
    ]),
], edition='January 2023', source='https://lawfaculty.du.ac.in/userfiles/downloads/LLBCM/VIth%20Term_Minor%20Acts%20and%20Supreme%20Courts%20Rules_LB%206034_2023.pdf',
   source_note='The cover uses LB-6034 while an internal page says LB-603. The stable node follows the catalog/cover code. State amendments and current Supreme Court practice directions require verification.',
   aliases=['LB-603 (internal page label)'],
   laws=['Registration Act, 1908', 'Indian Stamp Act, 1899', 'Court Fees Act, 1870', 'Suits Valuation Act, 1887', 'Supreme Court Rules, 2013', 'Transfer of Property Act, 1882'],
   prereq=['@lb-302.m19','@lb-502.m10','@lb-204.m12','@lb-401.m10'], elective=True, category='Procedure, conveyancing and court practice'),
]

# Build -----------------------------------------------------------------------

def slugify(value: str) -> str:
    value = value.lower().replace('’', '').replace("'", '')
    value = re.sub(r'[^a-z0-9]+', '-', value).strip('-')
    return value[:80] or 'node'


def note_anchor(node_id: str) -> str:
    return node_id.replace('.', '-').replace('_', '-')


def simple_eli15(title: str, subject: str = '') -> str:
    context = f' in {subject}' if subject else ''
    return (
        f'This is the rule or idea about {title.lower()}{context}. '
        'Ask what starts the rule, who must prove each fact, what exceptions apply, and what result follows.'
    )


def simple_summary(title: str, module: str, subject: str) -> str:
    return (
        f'Study “{title}” as part of {module} in {subject}. '
        'Map its legal source, elements, exceptions, proof, procedure and remedy before applying it to facts.'
    )


def clean_root() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)
    for folder in ['assets', 'data', 'notes', 'subjects', 'sources']:
        (ROOT / folder).mkdir(parents=True, exist_ok=True)


def build_graph() -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str], dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    subject_map: dict[str, dict[str, Any]] = {}
    module_last: dict[str, str] = {}
    subject_last: dict[str, str] = {}
    subject_first: dict[str, str] = {}
    subject_order: dict[str, int] = {}

    for idx, f in enumerate(FOUNDATIONS):
        node = dict(f)
        node.update({
            'learnable': True,
            'term': 0,
            'elective': False,
            'subjectId': None,
            'moduleId': None,
            'sourceStatus': 'method',
            'source': '',
            'notePath': f'notes/foundations.md#{note_anchor(f["id"])}',
            'breadcrumb': ['Foundation', f['title']],
            'position': idx + 1,
        })
        nodes[node['id']] = node

    for sidx, subject in enumerate(SUBJECTS):
        sid = subject['id']
        subject_order[sid] = sidx
        note_path = f'notes/{sid}.md'
        module_ids: list[str] = []
        total_items = 0
        prior_leaf: str | None = None
        first_leaf: str | None = None

        for midx, module in enumerate(subject['modules'], start=1):
            mid = f'{sid}.m{midx:02d}'
            module_ids.append(mid)
            children: list[str] = []
            module_first: str | None = None
            for tidx, title in enumerate(module['items'], start=1):
                tid = f'{mid}.s{tidx:02d}'
                if first_leaf is None:
                    first_leaf = tid
                if module_first is None:
                    module_first = tid
                children.append(tid)
                total_items += 1
                prereqs: list[str] = []
                if prior_leaf:
                    prereqs.append(prior_leaf)
                node = {
                    'id': tid,
                    'kind': 'topic',
                    'title': title,
                    'summary': simple_summary(title, module['title'], subject['title']),
                    'eli15': simple_eli15(title, subject['title']),
                    'learnable': True,
                    'subjectId': sid,
                    'subjectCode': subject['code'],
                    'subjectTitle': subject['title'],
                    'moduleId': mid,
                    'moduleTitle': module['title'],
                    'moduleNumber': midx,
                    'topicNumber': tidx,
                    'term': subject['term'],
                    'elective': subject['elective'],
                    'category': subject['category'],
                    'prerequisites': prereqs,
                    'background': [],
                    'related': [],
                    'tags': list(dict.fromkeys(module.get('tags', []) + [subject['category'], 'term-' + str(subject['term'])])),
                    'source': subject['source'],
                    'sourceStatus': subject['sourceStatus'],
                    'sourceNote': subject['sourceNote'],
                    'edition': subject['edition'],
                    'laws': subject['laws'],
                    'notePath': f'{note_path}#{note_anchor(tid)}',
                    'breadcrumb': [f'Term {subject["term"]}', subject['title'], module['title'], title],
                    'position': total_items,
                }
                nodes[tid] = node
                prior_leaf = tid
            assert module_first and prior_leaf
            module_last[mid] = prior_leaf
            nodes[mid] = {
                'id': mid,
                'kind': 'module',
                'title': module['title'],
                'summary': module.get('summary') or f'{len(children)} ordered nodes in {subject["title"]}.',
                'learnable': False,
                'subjectId': sid,
                'subjectCode': subject['code'],
                'subjectTitle': subject['title'],
                'term': subject['term'],
                'elective': subject['elective'],
                'category': subject['category'],
                'moduleNumber': midx,
                'children': children,
                'firstNode': module_first,
                'lastNode': prior_leaf,
                'prerequisites': [],
                'background': [],
                'related': [],
                'source': subject['source'],
                'sourceStatus': subject['sourceStatus'],
                'sourceNote': subject['sourceNote'],
                'edition': subject['edition'],
                'laws': subject['laws'],
                'notePath': f'{note_path}#{note_anchor(mid)}',
                'breadcrumb': [f'Term {subject["term"]}', subject['title'], module['title']],
            }

        assert first_leaf and prior_leaf
        subject_first[sid] = first_leaf
        subject_last[sid] = prior_leaf
        subject_node = {
            **{k: v for k, v in subject.items() if k != 'modules'},
            'kind': 'subject',
            'learnable': False,
            'moduleIds': module_ids,
            'firstNode': first_leaf,
            'lastNode': prior_leaf,
            'moduleCount': len(module_ids),
            'topicCount': total_items,
            'notePath': note_path,
            'prerequisites': [],
            'backgroundRefs': subject['background'],
            'relatedRefs': subject['related'],
            'breadcrumb': [f'Term {subject["term"]}', subject['title']],
        }
        nodes[sid] = subject_node
        subject_map[sid] = subject_node

    def resolve_strict(ref: str) -> str:
        raw = ref[1:] if ref.startswith('@') else ref
        raw = raw.lower()
        if raw in nodes and nodes[raw].get('learnable'):
            return raw
        if raw in subject_last:
            return subject_last[raw]
        if raw in module_last:
            return module_last[raw]
        raise ValueError(f'Unknown strict prerequisite reference: {ref}')

    def resolve_context(ref: str) -> str:
        raw = ref[1:] if ref.startswith('@') else ref
        raw = raw.lower()
        if raw in nodes:
            return raw
        raise ValueError(f'Unknown contextual reference: {ref}')

    for subject in SUBJECTS:
        sid = subject['id']
        resolved = list(dict.fromkeys(resolve_strict(ref) for ref in subject['prereq']))
        first = subject_first[sid]
        nodes[first]['prerequisites'] = list(dict.fromkeys(resolved + nodes[first]['prerequisites']))
        nodes[sid]['prerequisites'] = resolved
        nodes[sid]['background'] = [resolve_context(r) for r in subject['background']]
        nodes[sid]['related'] = [resolve_context(r) for r in subject['related']]
        for mid in nodes[sid]['moduleIds']:
            first_in_module = nodes[mid]['firstNode']
            nodes[mid]['prerequisites'] = nodes[first_in_module]['prerequisites']

    # Reverse edges and topological order for learnable nodes only.
    learnable_ids = [nid for nid, n in nodes.items() if n.get('learnable')]
    indegree = {nid: 0 for nid in learnable_ids}
    unlocks: dict[str, list[str]] = defaultdict(list)
    edges: list[dict[str, str]] = []
    for nid in learnable_ids:
        for pre in nodes[nid].get('prerequisites', []):
            if pre not in indegree:
                raise ValueError(f'{nid} depends on non-learnable or missing node {pre}')
            indegree[nid] += 1
            unlocks[pre].append(nid)
            edges.append({'from': pre, 'to': nid, 'type': 'prerequisite'})

    def priority(nid: str) -> tuple[int, int, int, int, int, str]:
        n = nodes[nid]
        if n['term'] == 0:
            return (0, 0, 0, 0, n.get('position', 0), nid)
        return (
            n['term'],
            1 if n['elective'] else 0,
            subject_order[n['subjectId']],
            n.get('moduleNumber', 0),
            n.get('topicNumber', 0),
            nid,
        )

    ready = sorted((nid for nid, d in indegree.items() if d == 0), key=priority)
    topo: list[str] = []
    level = {nid: 0 for nid in learnable_ids}
    while ready:
        nid = ready.pop(0)
        topo.append(nid)
        for nxt in sorted(unlocks.get(nid, []), key=priority):
            level[nxt] = max(level[nxt], level[nid] + 1)
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
                ready.sort(key=priority)
    if len(topo) != len(learnable_ids):
        blocked = [nid for nid, value in indegree.items() if value > 0][:30]
        raise ValueError(f'Strict prerequisite graph has a cycle; blocked sample: {blocked}')

    for rank, nid in enumerate(topo, start=1):
        nodes[nid]['learningOrder'] = rank
        nodes[nid]['level'] = level[nid]
        nodes[nid]['unlocks'] = sorted(unlocks.get(nid, []), key=priority)

    # Contextual edges are intentionally excluded from cycle control.
    contextual_edges: list[dict[str, str]] = []
    for sid, s in subject_map.items():
        for ref in s['background']:
            contextual_edges.append({'from': ref, 'to': sid, 'type': 'background'})
        for ref in s['related']:
            contextual_edges.append({'from': sid, 'to': ref, 'type': 'related'})

    # Subject-level overview edges. Multiple fine-grained prerequisites collapse into one edge.
    subject_edges_set: set[tuple[str, str]] = set()
    foundation_targets: set[str] = set()
    for s in SUBJECTS:
        for pre in nodes[s['id']]['prerequisites']:
            pre_node = nodes[pre]
            if pre_node.get('subjectId'):
                if pre_node['subjectId'] != s['id']:
                    subject_edges_set.add((pre_node['subjectId'], s['id']))
            else:
                foundation_targets.add(s['id'])
    subject_edges = [
        {'from': a, 'to': b, 'type': 'subject-prerequisite'}
        for a, b in sorted(subject_edges_set, key=lambda x: (subject_order[x[1]], subject_order[x[0]]))
    ]
    subject_edges += [
        {'from': 'foundation-spine', 'to': sid, 'type': 'subject-prerequisite'}
        for sid in sorted(foundation_targets, key=lambda x: subject_order[x])
    ]

    term_counts = {str(term): sum(1 for s in SUBJECTS if s['term'] == term) for term in range(1, 7)}
    stats = {
        'subjects': len(SUBJECTS),
        'coreSubjects': sum(1 for s in SUBJECTS if not s['elective']),
        'electiveSubjects': sum(1 for s in SUBJECTS if s['elective']),
        'modules': sum(len(s['modules']) for s in SUBJECTS),
        'topics': sum(len(m['items']) for s in SUBJECTS for m in s['modules']),
        'foundations': len(FOUNDATIONS),
        'learnableNodes': len(learnable_ids),
        'allNodes': len(nodes),
        'strictEdges': len(edges),
        'contextEdges': len(contextual_edges),
        'subjectEdges': len(subject_edges),
        'maxDepth': max(level.values()),
        'termCounts': term_counts,
    }

    # Assertions protect the published index against silent omissions.
    assert len(SUBJECTS) == 45
    assert term_counts == {'1': 5, '2': 5, '3': 7, '4': 10, '5': 10, '6': 8}
    assert len(nodes) == len(set(nodes))
    assert all(n['parent'] in nodes for n in [] if n.get('parent'))
    assert all(s['source'] for s in SUBJECTS)
    assert len(topo) == stats['learnableNodes']

    subjects_for_data = []
    for s in SUBJECTS:
        subject_node = nodes[s['id']]
        subjects_for_data.append({
            k: subject_node[k] for k in [
                'id', 'code', 'catalogCode', 'term', 'title', 'elective', 'edition', 'source',
                'sourceStatus', 'sourceNote', 'aliases', 'laws', 'category', 'kind', 'moduleIds',
                'firstNode', 'lastNode', 'moduleCount', 'topicCount', 'notePath', 'prerequisites',
                'background', 'related', 'breadcrumb'
            ]
        })

    # Serialize a normalized graph. Subject metadata is stored once and hydrated by the app,
    # which keeps the initial mobile payload far smaller than repeating source data on 3,800 topics.
    public_nodes: dict[str, dict[str, Any]] = {}
    foundation_keys = ['id','title','kind','summary','eli15','prerequisites','tags','learnable','term','elective','notePath','learningOrder','level','unlocks']
    subject_keys = ['id','kind','title','learnable','moduleIds','firstNode','lastNode','moduleCount','topicCount','notePath','prerequisites','background','related']
    module_keys = ['id','kind','title','summary','learnable','subjectId','moduleNumber','children','firstNode','lastNode','prerequisites','notePath']
    topic_keys = ['id','kind','title','summary','eli15','learnable','subjectId','moduleId','moduleNumber','topicNumber','prerequisites','notePath','learningOrder','level','unlocks']
    for nid, node in nodes.items():
        if node.get('term') == 0:
            keys = foundation_keys
        elif node['kind'] == 'subject':
            keys = subject_keys
        elif node['kind'] == 'module':
            keys = module_keys
        else:
            keys = topic_keys
        public_nodes[nid] = {key: node[key] for key in keys if key in node}

    data = {
        'meta': {
            'title': 'DU LL.B. Knowledge Graph',
            'description': 'A mobile-first prerequisite DAG and note index for the University of Delhi LL.B. course-material catalog.',
            'generated': '2026-08-06',
            'canonicalCatalog': CATALOG_URL,
            'repository': f'https://github.com/{REPO}',
            'edgeSemantics': {
                'prerequisite': 'May be assumed by the target node and therefore controls learning order.',
                'background': 'Helpful but not required; does not control learning order.',
                'related': 'Cross-reference only; may point in either direction and may be cyclic.',
            },
            'stats': stats,
        },
        'subjects': subjects_for_data,
        'nodes': public_nodes,
        'edges': edges + contextual_edges,
        'subjectEdges': subject_edges,
        'learningOrder': topo,
    }
    validation = {
        'valid': True,
        'checks': {
            'subjectCount': len(SUBJECTS) == 45,
            'termDistribution': term_counts == {'1': 5, '2': 5, '3': 7, '4': 10, '5': 10, '6': 8},
            'uniqueNodeIds': len(nodes) == len(set(nodes)),
            'allStrictReferencesResolve': True,
            'acyclicStrictGraph': len(topo) == len(learnable_ids),
            'allSourcesPresent': all(s['source'] for s in SUBJECTS),
            'everySubjectHasModules': all(s['modules'] for s in SUBJECTS),
            'everyModuleHasTopics': all(m['items'] for s in SUBJECTS for m in s['modules']),
        },
        'stats': stats,
        'warnings': [
            'LB-504 is the stable catalog identity although its linked PDF labels the paper LB-604 and VI Term.',
            'LB-501 uses the best available official DU 2025 material because the exact 2026-27 target was unavailable.',
            'LB-4035 and LB-602 use official DU archive editions.',
            'LB-404 and LB-4031 are course structures rather than full casebooks.',
            'A source edition is not proof that every cited rule remains current; each substantive note requires a current-law check.',
        ],
    }
    return data, nodes, topo, validation


def md_link_for_node(node_id: str, nodes: dict[str, dict[str, Any]]) -> str:
    node = nodes[node_id]
    label = node['title']
    if node.get('subjectCode'):
        label = f'{node["subjectCode"]}: {label}'
    return f'[{label}](../index.html#node={node_id})'


def generate_notes(data: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> None:
    foundations = [nodes[f['id']] for f in FOUNDATIONS]
    lines = [
        '# Common legal-method spine', '',
        'These nodes are strict prerequisites shared by several papers. They are deliberately small so later notes may assume only the skills already reached in the graph.', '',
    ]
    for n in foundations:
        lines += [
            f'<a id="{note_anchor(n["id"])}"></a>',
            f'## {n["id"].upper()} — {n["title"]}', '',
            f'**ELI15:** {n["eli15"]}', '',
            n['summary'], '',
            '**Build this note with:** definition; purpose; a worked example; failure modes; primary sources; a one-page visual; a recall check; and links to every subject that uses it.', '',
        ]
    (ROOT / 'notes' / 'foundations.md').write_text('\n'.join(lines), encoding='utf-8')

    scaffold = [
        '- **Rule in one sentence:** State the narrow proposition and its jurisdiction.',
        '- **Elements / test:** Convert the rule into numbered factual questions.',
        '- **Exceptions / defences:** Show what defeats or changes the rule.',
        '- **Authority:** Add the statute, section, leading holding and later treatment.',
        '- **Proof and procedure:** Identify burden, standard, forum, stage and limitation.',
        '- **Remedy / consequence:** State the order, liability, sanction or legal effect.',
        '- **ELI15 example:** Use one concrete everyday fact pattern, then explain where the analogy breaks.',
        '- **Visual:** Add a flowchart, timeline, comparison table, element map or institutional diagram.',
        '- **Exam use:** Add common issue triggers, a model issue statement and a short application.',
        '- **Currency check:** Verify commencement, amendment, repeal, rules, notifications and binding later cases.',
    ]
    for subject in SUBJECTS:
        sid = subject['id']
        sn = nodes[sid]
        lines = [
            '---',
            f'id: {sid}',
            f'code: {subject["code"]}',
            f'title: "{subject["title"].replace(chr(34), chr(39))}"',
            f'term: {subject["term"]}',
            f'elective: {str(subject["elective"]).lower()}',
            f'edition: "{subject["edition"].replace(chr(34), chr(39))}"',
            'status: scaffold',
            '---', '',
            f'# {subject["code"]} — {subject["title"]}', '',
            f'**Term:** {subject["term"]} · **Type:** {"Elective" if subject["elective"] else "Core"} · **Edition:** {subject["edition"] or "Not stated"}', '',
            f'**Official source:** {subject["source"]}', '',
        ]
        if subject['sourceNote']:
            lines += [f'> Source note: {subject["sourceNote"]}', '']
        lines += [
            '## How to use this file', '',
            'Each heading below is a stable node in the curriculum DAG. The present text is a structured enrichment scaffold, not a claim that the substantive note is complete. Add quotations only within copyright limits and always identify the source and pinpoint.', '',
            '## Strict prerequisites', '',
        ]
        if sn['prerequisites']:
            for pre in sn['prerequisites']:
                lines.append(f'- {md_link_for_node(pre, nodes)}')
        else:
            lines.append('- None beyond the common orientation.')
        lines += ['', '## Principal legislation and instruments', '']
        if subject['laws']:
            lines += [f'- {law}' for law in subject['laws']]
        else:
            lines.append('- Add primary authorities during enrichment.')
        lines += ['', '## Module map', '']
        for mid in sn['moduleIds']:
            m = nodes[mid]
            lines.append(f'- [{m["moduleNumber"]}. {m["title"]}](#{note_anchor(mid)}) — {len(m["children"])} nodes')
        lines.append('')

        for mid in sn['moduleIds']:
            m = nodes[mid]
            lines += [
                f'<a id="{note_anchor(mid)}"></a>',
                f'## {m["moduleNumber"]}. {m["title"]}', '',
                f'{m["summary"]}', '',
            ]
            for tid in m['children']:
                n = nodes[tid]
                lines += [
                    f'<a id="{note_anchor(tid)}"></a>',
                    f'### {m["moduleNumber"]}.{n["topicNumber"]} {n["title"]}', '',
                    f'**Node:** `{tid}` · **Status:** scaffold', '',
                    f'**ELI15:** {n["eli15"]}', '',
                    f'**Scope:** {n["summary"]}', '',
                    '**Enrichment checklist**', '',
                    *scaffold, '',
                ]
        (ROOT / 'notes' / f'{sid}.md').write_text('\n'.join(lines), encoding='utf-8')


def generate_subject_indexes(data: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> None:
    for subject in data['subjects']:
        sid = subject['id']
        d = ROOT / 'subjects' / sid
        d.mkdir(parents=True, exist_ok=True)
        lines = [
            f'# {subject["code"]} — {subject["title"]}', '',
            f'Term {subject["term"]} · {"Elective" if subject["elective"] else "Core"} · {subject["moduleCount"]} modules · {subject["topicCount"]} topic nodes', '',
            f'[Open in the interactive graph](../../index.html#node={sid}) · [Open note scaffold](../../{subject["notePath"]}) · [Official source]({subject["source"]})', '',
        ]
        if subject['sourceNote']:
            lines += [f'> {subject["sourceNote"]}', '']
        for mid in subject['moduleIds']:
            m = nodes[mid]
            lines += [f'## {m["moduleNumber"]}. {m["title"]}', '']
            for child in m['children']:
                n = nodes[child]
                lines.append(f'- [{n["title"]}](../../index.html#node={child})')
            lines.append('')
        (d / 'README.md').write_text('\n'.join(lines), encoding='utf-8')


def generate_docs(data: dict[str, Any], validation: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> None:
    stats = data['meta']['stats']
    readme = f'''# DU LL.B. Knowledge Graph

A mobile-first, static prerequisite graph and note index for the University of Delhi LL.B. course-material catalog.

[Open the deployed index](https://legedith.github.io/llb/) · [Open the canonical DU catalog]({CATALOG_URL})

## What is here

- {stats['subjects']} papers across six terms: {stats['coreSubjects']} core and {stats['electiveSubjects']} elective.
- {stats['modules']} modules and {stats['topics']} syllabus-derived topic nodes.
- {stats['foundations']} common legal-method nodes.
- {stats['strictEdges']} strict prerequisite edges, validated as a directed acyclic graph.
- Separate background and related edges, which never block progress.
- One stable Markdown note scaffold per paper, with an anchor for every topic node.
- Source, edition, code-alias and current-law warnings kept in node metadata.

## The key design rule

A strict prerequisite is material a later node may assume. Background reading is useful but optional. A related link is only a cross-reference. Keeping these relations separate prevents the rich legal cross-reference network from creating false learning cycles.

The DU term order is preserved for source fidelity. The learning view uses a topological order derived from strict prerequisites. These are intentionally different views.

## Repository map

- `index.html`, `styles.css`, `app.js`: zero-dependency mobile-first application.
- `data/curriculum.json`: complete machine-readable graph.
- `data/schema.md`: node and edge contract.
- `data/validation-report.json`: generated integrity checks and known source warnings.
- `notes/`: common foundations plus 45 subject note scaffolds.
- `subjects/`: human-readable subject indexes.
- `sources/README.md`: source register.

## Source discipline

The linked DU PDFs are course material, not proof of current law. Before a substantive note is treated as current, verify commencement, amendment, repeal, replacement codes, rules, notifications, binding later judgments and jurisdiction. Archive and outline-only sources are labelled rather than silently upgraded.

Do not mirror or reproduce substantial copyrighted course material. Quote only what is necessary, use pinpoint attribution, prefer public-domain primary law, and write original explanations.

## Local preview

```bash
python -m http.server 8000
```

Open `http://localhost:8000/`. The site uses no build step.
'''
    (ROOT / 'README.md').write_text(readme, encoding='utf-8')

    schema = '''# Curriculum graph schema

`data/curriculum.json` is the canonical machine-readable index.

## Node kinds

- `foundation` or `skill`: common learnable method node.
- `subject`: non-learnable paper container.
- `module`: non-learnable unit or topic-group container.
- `topic`: smallest learnable syllabus node.

Every learnable node has `prerequisites`, `unlocks`, `learningOrder`, `level`, `summary`, `eli15`, source metadata and a stable `notePath`.

## Edge kinds

- `prerequisite`: strict directed edge. The target may assume the source. These edges alone form the DAG and determine unlocks.
- `background`: useful prior knowledge but not required.
- `related`: navigational cross-reference; direction does not imply dependency.
- `subject-prerequisite`: collapsed overview edge between papers, stored separately in `subjectEdges`.

## Stable identity

Internal IDs use lower-case catalog identities such as `lb-102`, module IDs such as `lb-102.m01`, and topic IDs such as `lb-102.m01.s01`. Display codes and aliases may change without breaking links.
'''
    (ROOT / 'data' / 'schema.md').write_text(schema, encoding='utf-8')
    (ROOT / 'data' / 'validation-report.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding='utf-8')

    template = '''# Note enrichment template

Use this order for every node so that explanations remain comparable across subjects.

1. One-sentence rule and jurisdiction.
2. ELI15 explanation, followed by the limit of the analogy.
3. Why the rule exists and the interests it protects.
4. Elements, tests, burdens and standards.
5. Exceptions, defences, provisos and competing rules.
6. Primary legislation with current section text or a precise link.
7. Leading cases: material facts, issue, holding, ratio, reasoning, order and later treatment.
8. Procedure, forum, limitation, evidence and remedy.
9. Worked fact patterns from easy to hard.
10. Visual: flowchart, timeline, comparison matrix, institutional map or decision tree.
11. Exam and practice guide: issue triggers, common traps, drafting or advocacy use.
12. Cross-references and a dated current-law check.

Never use a quotation without source and pinpoint. Mark paraphrase as paraphrase. Mark uncertainty and conflicts between authorities explicitly.
'''
    (ROOT / 'notes' / '_template.md').write_text(template, encoding='utf-8')

    contributing = '''# Contributing notes

Keep the graph stable and improve content behind stable node IDs.

Before editing a node, verify its strict prerequisites. Do not assume a concept that is neither explained in the node nor reachable through a prerequisite edge. Add optional material as `background` or `related`, not as a strict prerequisite.

Every legal proposition needs primary authority where reasonably available. Record jurisdiction, court, date, paragraph or section, and current status. Distinguish source text, quotation, paraphrase, explanation and opinion. Do not paste course packs or commercial commentary.

For visuals, include alt text and a text equivalent. For tables, keep the first column meaningful on a narrow screen. Test at 390 px width.
'''
    (ROOT / 'CONTRIBUTING.md').write_text(contributing, encoding='utf-8')

    source_lines = [
        '# Source register', '',
        f'Canonical catalog: {CATALOG_URL}', '',
        'The source register records what defined the initial node map. It is not a statement that every source is current law.', '',
        '| Term | Paper | Type | Edition | Status | Source note |',
        '|---:|---|---|---|---|---|',
    ]
    for s in data['subjects']:
        status = s['sourceStatus']
        note = (s['sourceNote'] or 'Official DU material.').replace('|', '\\|')
        source_lines.append(f'| {s["term"]} | [{s["code"]} — {s["title"]}]({s["source"]}) | {"Elective" if s["elective"] else "Core"} | {s["edition"]} | {status} | {note} |')
    source_lines += ['', '## Known identity and edition issues', '',
        '- LB-504 Taxation is the stable catalog identity; its linked PDF labels the paper LB-604 and VI Term.',
        '- LB-501 is based on the best available official DU 2025 material because the exact 2026–27 file was unavailable.',
        '- LB-4035 and LB-602 use official DU archive copies.',
        '- LB-404 and LB-4031 provide course structures rather than full casebooks.',
        '- Older elective materials remain useful for the syllabus map but require a present-law check before doctrinal use.',
    ]
    (ROOT / 'sources' / 'README.md').write_text('\n'.join(source_lines), encoding='utf-8')


def write_data(data: dict[str, Any]) -> None:
    (ROOT / 'data' / 'curriculum.json').write_text(
        json.dumps(data, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )

def generate_web_assets() -> None:
    index_html = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#f6f1e7">
  <meta name="description" content="A mobile-first prerequisite DAG and note index for the University of Delhi LL.B. course materials.">
  <title>DU LL.B. Knowledge Graph</title>
  <link rel="manifest" href="manifest.webmanifest">
  <link rel="icon" href="assets/icon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <a class="skip-link" href="#main">Skip to the knowledge graph</a>
  <header class="site-header">
    <div class="brand-row">
      <button id="menuButton" class="icon-button menu-button" type="button" aria-label="Open filters" aria-controls="filterPanel" aria-expanded="false">
        <span aria-hidden="true">☰</span>
      </button>
      <a class="brand" href="./" aria-label="DU LL.B. Knowledge Graph home">
        <span class="brand-mark" aria-hidden="true">§</span>
        <span><strong>LL.B. Graph</strong><small>DU course-material index</small></span>
      </a>
      <button id="aboutButton" class="icon-button" type="button" aria-label="About this index">?</button>
    </div>
    <form id="searchForm" class="search-shell" role="search">
      <label class="sr-only" for="searchInput">Search subjects, topics, laws and aliases</label>
      <span class="search-symbol" aria-hidden="true">⌕</span>
      <input id="searchInput" type="search" autocomplete="off" spellcheck="false" placeholder="Search 4,000+ nodes…">
      <button id="searchClear" class="search-clear" type="button" aria-label="Clear search" hidden>×</button>
    </form>
    <div id="searchResults" class="search-results" hidden></div>
  </header>

  <aside id="filterPanel" class="filter-panel" aria-label="Filters" aria-hidden="true">
    <div class="panel-heading">
      <div><span class="eyebrow">VIEW CONTROLS</span><h2>Filter the map</h2></div>
      <button id="closeFilters" class="icon-button" type="button" aria-label="Close filters">×</button>
    </div>
    <fieldset>
      <legend>Term</legend>
      <div id="termFilters" class="chip-grid"></div>
    </fieldset>
    <fieldset>
      <legend>Paper type</legend>
      <label class="check-row"><input id="coreFilter" type="checkbox" checked> Core papers</label>
      <label class="check-row"><input id="electiveFilter" type="checkbox" checked> Electives</label>
    </fieldset>
    <fieldset>
      <legend>Node state</legend>
      <label class="check-row"><input id="availableFilter" type="checkbox"> Ready to learn now</label>
      <label class="check-row"><input id="bookmarkedFilter" type="checkbox"> Bookmarked only</label>
    </fieldset>
    <button id="resetFilters" class="button secondary full" type="button">Reset filters</button>
  </aside>
  <div id="panelScrim" class="scrim" hidden></div>

  <main id="main" tabindex="-1">
    <section id="learnView" class="view active" data-view="learn" aria-labelledby="learnTitle">
      <div class="hero">
        <p class="eyebrow">LEARN IN DEPENDENCY ORDER</p>
        <h1 id="learnTitle">Start with what the next idea is allowed to assume.</h1>
        <p>The syllabus order is preserved, but this path follows strict prerequisites. Background and related links never block you.</p>
        <div id="statsStrip" class="stats-strip" aria-label="Curriculum statistics"></div>
      </div>
      <section class="section-block" aria-labelledby="nextTitle">
        <div class="section-heading">
          <div><p class="eyebrow">NEXT NODES</p><h2 id="nextTitle">Ready now</h2></div>
          <button id="resumeButton" class="text-button" type="button">Resume last</button>
        </div>
        <div id="readyList" class="card-list"></div>
      </section>
      <section class="section-block" aria-labelledby="pathTitle">
        <div class="section-heading">
          <div><p class="eyebrow">GRADUAL PATH</p><h2 id="pathTitle">Your learning queue</h2></div>
          <span id="progressLabel" class="quiet-label"></span>
        </div>
        <div id="learningQueue" class="timeline"></div>
      </section>
      <section class="section-block principle-box" aria-labelledby="edgeTitle">
        <p class="eyebrow">EDGE DISCIPLINE</p>
        <h2 id="edgeTitle">Three links, three meanings</h2>
        <div class="legend-grid">
          <div><span class="edge-key strict"></span><strong>Prerequisite</strong><p>The target may assume it. Controls order.</p></div>
          <div><span class="edge-key background"></span><strong>Background</strong><p>Helpful, but the target must still explain itself.</p></div>
          <div><span class="edge-key related"></span><strong>Related</strong><p>A cross-reference only. Cycles are allowed.</p></div>
        </div>
      </section>
    </section>

    <section id="browseView" class="view" data-view="browse" aria-labelledby="browseTitle" hidden>
      <div class="view-intro">
        <p class="eyebrow">SOURCE-FIDELITY VIEW</p>
        <h1 id="browseTitle">Browse the DU syllabus</h1>
        <p>Open a term, paper, module or topic. Every topic has a stable ID and a note anchor.</p>
      </div>
      <div id="browseSummary" class="filter-summary"></div>
      <div id="catalogTree" class="catalog-tree"></div>
    </section>

    <section id="graphView" class="view" data-view="graph" aria-labelledby="graphTitle" hidden>
      <div class="view-intro">
        <p class="eyebrow">INFORMATION NETWORK</p>
        <h1 id="graphTitle">See why a node comes next</h1>
        <p>The overview collapses topic-level edges into paper dependencies. Select any node for its exact local graph.</p>
      </div>
      <section class="graph-panel" aria-labelledby="overviewTitle">
        <div class="section-heading">
          <div><p class="eyebrow">45-PAPER OVERVIEW</p><h2 id="overviewTitle">Curriculum lanes</h2></div>
          <div class="zoom-controls" aria-label="Graph scale">
            <button id="graphSmaller" class="icon-button" type="button" aria-label="Make graph smaller">−</button>
            <button id="graphLarger" class="icon-button" type="button" aria-label="Make graph larger">+</button>
          </div>
        </div>
        <div id="subjectGraphWrap" class="subject-graph-wrap" tabindex="0" aria-label="Scrollable subject prerequisite graph">
          <svg id="subjectGraph" role="img" aria-labelledby="subjectGraphTitle subjectGraphDesc"></svg>
        </div>
        <p class="graph-note">Lines show strict paper-level prerequisites. Foundation dependencies enter from the method spine. Tap a paper to inspect it.</p>
      </section>
      <section class="graph-panel" aria-labelledby="focusTitle">
        <div class="section-heading">
          <div><p class="eyebrow">FOCUS GRAPH</p><h2 id="focusTitle">Exact prerequisites and unlocks</h2></div>
          <button id="chooseFocus" class="text-button" type="button">Choose node</button>
        </div>
        <div id="focusGraph" class="focus-graph"></div>
      </section>
    </section>

    <section id="sourcesView" class="view" data-view="sources" aria-labelledby="sourcesTitle" hidden>
      <div class="view-intro">
        <p class="eyebrow">PROVENANCE AND CURRENCY</p>
        <h1 id="sourcesTitle">Know what each node rests on</h1>
        <p>A course pack defines this initial map; it does not prove that the law remains in force. Archive, outline-only and code-conflict notes stay visible.</p>
      </div>
      <div class="source-callout">
        <strong>Current-law rule</strong>
        <p>Before relying on a note, check commencement, amendments, replacement codes, rules, notifications and binding later decisions.</p>
      </div>
      <div id="sourceRegister" class="source-register"></div>
    </section>
  </main>

  <nav class="bottom-nav" aria-label="Primary navigation">
    <button class="nav-item active" type="button" data-target="learn" aria-current="page"><span aria-hidden="true">↗</span><span>Learn</span></button>
    <button class="nav-item" type="button" data-target="browse"><span aria-hidden="true">≡</span><span>Browse</span></button>
    <button class="nav-item" type="button" data-target="graph"><span aria-hidden="true">⌘</span><span>Graph</span></button>
    <button class="nav-item" type="button" data-target="sources"><span aria-hidden="true">¶</span><span>Sources</span></button>
  </nav>

  <dialog id="nodeDialog" class="node-dialog">
    <div class="dialog-handle" aria-hidden="true"></div>
    <div class="dialog-head">
      <div id="nodeBreadcrumb" class="breadcrumb"></div>
      <button id="closeNode" class="icon-button" type="button" aria-label="Close node">×</button>
    </div>
    <div id="nodeContent" class="node-content"></div>
  </dialog>

  <dialog id="aboutDialog" class="about-dialog">
    <div class="dialog-head"><div><p class="eyebrow">ABOUT</p><h2>What this index claims</h2></div><button id="closeAbout" class="icon-button" type="button" aria-label="Close about">×</button></div>
    <p>This is a structured starting map of the DU LL.B. course-material catalog. It distinguishes source order from prerequisite order and preserves edition warnings. The Markdown files are enrichment scaffolds, not completed legal notes.</p>
    <p>The strict graph is validated as acyclic. Related legal ideas may still point to each other because law is a network, not a simple textbook list.</p>
    <a class="button secondary full" href="README.md">Read repository guide</a>
  </dialog>

  <div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
  <script src="app.js" defer></script>
</body>
</html>
'''
    (ROOT / 'index.html').write_text(index_html, encoding='utf-8')

    css = r''':root {
  --paper: #f6f1e7;
  --paper-2: #fffdf8;
  --ink: #201f1b;
  --muted: #68645c;
  --line: #d9d1c3;
  --line-strong: #aaa08f;
  --accent: #274c3b;
  --accent-soft: #dfeae3;
  --accent-2: #8b3f2f;
  --accent-2-soft: #f0e2dd;
  --gold: #8d6b28;
  --gold-soft: #eee5cf;
  --blue: #315b72;
  --blue-soft: #e0ebf0;
  --shadow: 0 14px 42px rgba(37, 31, 23, .13);
  --radius: 18px;
  --header-h: 128px;
  --nav-h: 72px;
  color-scheme: light;
}
* { box-sizing: border-box; }
html { background: var(--paper); color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; scroll-behavior: smooth; }
body { margin: 0; min-height: 100vh; background:
  radial-gradient(circle at 100% 0, rgba(139,63,47,.07), transparent 28rem),
  linear-gradient(180deg, var(--paper-2) 0, var(--paper) 22rem); }
button, input { font: inherit; }
button, a { -webkit-tap-highlight-color: transparent; }
a { color: inherit; }
button { color: inherit; }
.sr-only { position: absolute !important; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.skip-link { position: fixed; z-index: 1000; top: .5rem; left: .5rem; transform: translateY(-140%); background: var(--ink); color: white; padding: .75rem 1rem; border-radius: .5rem; }
.skip-link:focus { transform: translateY(0); }
.site-header { position: sticky; top: 0; z-index: 30; padding: max(.65rem, env(safe-area-inset-top)) 1rem .7rem; background: rgba(255,253,248,.94); backdrop-filter: blur(18px); border-bottom: 1px solid rgba(217,209,195,.85); }
.brand-row { display: grid; grid-template-columns: 42px 1fr 42px; align-items: center; gap: .6rem; max-width: 1180px; margin: 0 auto .65rem; }
.brand { display: inline-flex; align-items: center; justify-content: center; gap: .55rem; text-decoration: none; min-width: 0; }
.brand-mark { display: grid; place-items: center; width: 34px; height: 34px; border: 1px solid var(--ink); border-radius: 50%; font-family: Georgia, serif; font-size: 1.4rem; }
.brand span:last-child { display: grid; line-height: 1.05; }
.brand strong { letter-spacing: -.025em; }
.brand small { margin-top: .25rem; color: var(--muted); font-size: .67rem; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; }
.icon-button { display: inline-grid; place-items: center; width: 42px; height: 42px; border-radius: 50%; border: 1px solid var(--line); background: var(--paper-2); cursor: pointer; }
.icon-button:hover, .icon-button:focus-visible { border-color: var(--accent); outline: 3px solid var(--accent-soft); }
.search-shell { position: relative; display: flex; align-items: center; max-width: 760px; margin: 0 auto; }
.search-shell input { width: 100%; min-height: 46px; border: 1px solid var(--line); border-radius: 14px; background: white; color: var(--ink); padding: .75rem 2.7rem .75rem 2.5rem; outline: none; box-shadow: 0 3px 12px rgba(35,31,25,.04); }
.search-shell input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
.search-symbol { position: absolute; left: .9rem; font-size: 1.35rem; color: var(--muted); transform: translateY(-1px); }
.search-clear { position: absolute; right: .5rem; width: 34px; height: 34px; border: 0; border-radius: 50%; background: transparent; font-size: 1.45rem; cursor: pointer; }
.search-results { position: absolute; z-index: 40; top: calc(100% - .1rem); left: 1rem; right: 1rem; max-width: 760px; max-height: min(65vh, 520px); margin: 0 auto; overflow: auto; background: white; border: 1px solid var(--line); border-radius: 0 0 16px 16px; box-shadow: var(--shadow); }
.search-result { display: grid; grid-template-columns: auto 1fr auto; gap: .7rem; align-items: start; width: 100%; padding: .8rem .9rem; border: 0; border-bottom: 1px solid #eee8de; background: white; text-align: left; cursor: pointer; }
.search-result:hover, .search-result:focus-visible { background: var(--accent-soft); outline: none; }
.search-result:last-child { border-bottom: 0; }
.search-result .code { min-width: 3.7rem; color: var(--accent); font-size: .72rem; font-weight: 800; letter-spacing: .05em; }
.search-result strong { display: block; font-size: .9rem; }
.search-result small { display: block; margin-top: .18rem; color: var(--muted); line-height: 1.35; }
.search-result .kind { color: var(--muted); font-size: .7rem; text-transform: uppercase; }
main { width: min(100%, 1180px); margin: 0 auto; padding: 0 1rem calc(var(--nav-h) + 2rem + env(safe-area-inset-bottom)); }
.view { animation: reveal .2s ease-out; }
@keyframes reveal { from { opacity: 0; transform: translateY(4px); } }
.hero, .view-intro { padding: 2.2rem 0 1.35rem; }
.hero h1, .view-intro h1 { max-width: 760px; margin: .25rem 0 .75rem; font-family: Georgia, "Times New Roman", serif; font-size: clamp(2.1rem, 9vw, 4.6rem); line-height: .98; letter-spacing: -.045em; font-weight: 600; }
.view-intro h1 { font-size: clamp(2rem, 8vw, 3.8rem); }
.hero > p:last-of-type, .view-intro > p:last-child { max-width: 720px; margin: 0; color: var(--muted); line-height: 1.55; }
.eyebrow { margin: 0 0 .3rem; color: var(--accent-2); font-size: .68rem; font-weight: 850; letter-spacing: .14em; text-transform: uppercase; }
.stats-strip { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .6rem; margin-top: 1.4rem; }
.stat { padding: .85rem; border: 1px solid var(--line); border-radius: 14px; background: rgba(255,255,255,.6); }
.stat strong { display: block; font-family: Georgia, serif; font-size: 1.55rem; font-weight: 600; }
.stat span { color: var(--muted); font-size: .75rem; }
.section-block { margin: 1rem 0 2.2rem; }
.section-heading { display: flex; align-items: end; justify-content: space-between; gap: 1rem; margin-bottom: .9rem; }
.section-heading h2, .panel-heading h2, .dialog-head h2 { margin: 0; font-family: Georgia, serif; font-size: 1.55rem; font-weight: 600; letter-spacing: -.025em; }
.text-button { border: 0; border-bottom: 1px solid currentColor; background: transparent; color: var(--accent); padding: .25rem 0; font-weight: 750; cursor: pointer; white-space: nowrap; }
.card-list { display: grid; gap: .75rem; }
.node-card { position: relative; display: grid; grid-template-columns: 42px 1fr auto; gap: .8rem; align-items: start; width: 100%; padding: .95rem; border: 1px solid var(--line); border-radius: var(--radius); background: var(--paper-2); text-align: left; box-shadow: 0 4px 18px rgba(48,41,31,.05); cursor: pointer; }
.node-card:hover, .node-card:focus-visible { border-color: var(--accent); outline: 3px solid var(--accent-soft); }
.node-card.complete { opacity: .72; }
.node-card .ordinal { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 12px; background: var(--accent-soft); color: var(--accent); font-size: .72rem; font-weight: 850; text-align: center; }
.node-card .node-main { min-width: 0; }
.node-card h3 { margin: .05rem 0 .28rem; font-size: 1rem; line-height: 1.25; }
.node-card p { display: -webkit-box; overflow: hidden; margin: 0; color: var(--muted); font-size: .82rem; line-height: 1.4; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.node-card .meta { display: flex; flex-wrap: wrap; gap: .3rem .6rem; margin-top: .55rem; color: var(--muted); font-size: .69rem; }
.node-card .arrow { align-self: center; color: var(--line-strong); font-size: 1.2rem; }
.timeline { position: relative; display: grid; gap: .5rem; }
.timeline::before { content: ""; position: absolute; top: .8rem; bottom: .8rem; left: 16px; width: 1px; background: var(--line); }
.timeline-row { position: relative; display: grid; grid-template-columns: 33px 1fr; gap: .75rem; align-items: start; width: 100%; border: 0; background: transparent; padding: .5rem 0; text-align: left; cursor: pointer; }
.timeline-dot { z-index: 1; display: grid; place-items: center; width: 33px; height: 33px; border: 1px solid var(--line-strong); border-radius: 50%; background: var(--paper); color: var(--muted); font-size: .68rem; font-weight: 800; }
.timeline-row.ready .timeline-dot { background: var(--accent); border-color: var(--accent); color: white; }
.timeline-row.complete .timeline-dot { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
.timeline-copy strong { display: block; font-size: .9rem; line-height: 1.3; }
.timeline-copy small { display: block; margin-top: .2rem; color: var(--muted); line-height: 1.35; }
.quiet-label { color: var(--muted); font-size: .75rem; }
.principle-box { padding: 1.1rem; border: 1px solid var(--line); border-radius: var(--radius); background: linear-gradient(145deg, rgba(255,255,255,.72), rgba(223,234,227,.45)); }
.principle-box h2 { margin: .25rem 0 1rem; font-family: Georgia, serif; }
.legend-grid { display: grid; gap: .9rem; }
.legend-grid > div { display: grid; grid-template-columns: 38px 1fr; gap: .1rem .65rem; }
.legend-grid p { grid-column: 2; margin: 0; color: var(--muted); font-size: .78rem; }
.edge-key { align-self: center; display: block; width: 34px; height: 3px; border-radius: 2px; }
.edge-key.strict { background: var(--accent); }
.edge-key.background { background: repeating-linear-gradient(90deg, var(--blue), var(--blue) 5px, transparent 5px, transparent 9px); }
.edge-key.related { background: repeating-linear-gradient(90deg, var(--gold), var(--gold) 2px, transparent 2px, transparent 6px); }
.filter-panel { position: fixed; z-index: 80; inset: 0 auto 0 0; width: min(88vw, 380px); padding: max(1.1rem, env(safe-area-inset-top)) 1rem calc(1.4rem + env(safe-area-inset-bottom)); overflow-y: auto; background: var(--paper-2); box-shadow: var(--shadow); transform: translateX(-105%); transition: transform .2s ease; }
.filter-panel.open { transform: translateX(0); }
.panel-heading, .dialog-head { display: flex; align-items: start; justify-content: space-between; gap: 1rem; }
.filter-panel fieldset { margin: 1.35rem 0; padding: 0; border: 0; }
.filter-panel legend { margin-bottom: .65rem; font-weight: 800; }
.chip-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: .45rem; }
.filter-chip { min-height: 40px; border: 1px solid var(--line); border-radius: 999px; background: white; cursor: pointer; }
.filter-chip.active { background: var(--accent); border-color: var(--accent); color: white; }
.check-row { display: flex; align-items: center; gap: .7rem; min-height: 42px; }
.check-row input { width: 18px; height: 18px; accent-color: var(--accent); }
.scrim { position: fixed; z-index: 70; inset: 0; background: rgba(25,23,19,.38); backdrop-filter: blur(2px); }
.button { display: inline-flex; justify-content: center; align-items: center; min-height: 44px; padding: .72rem 1rem; border: 1px solid var(--accent); border-radius: 12px; background: var(--accent); color: white; font-weight: 800; text-decoration: none; cursor: pointer; }
.button.secondary { background: transparent; color: var(--accent); }
.button.danger { border-color: var(--accent-2); background: transparent; color: var(--accent-2); }
.full { width: 100%; }
.filter-summary { display: flex; flex-wrap: wrap; gap: .45rem; margin: .1rem 0 1rem; color: var(--muted); font-size: .78rem; }
.summary-pill { padding: .35rem .6rem; border: 1px solid var(--line); border-radius: 999px; background: rgba(255,255,255,.6); }
.catalog-tree { display: grid; gap: 1rem; }
.term-block { border: 1px solid var(--line); border-radius: var(--radius); background: rgba(255,255,255,.5); overflow: clip; }
.term-summary { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1rem; cursor: pointer; list-style: none; }
.term-summary::-webkit-details-marker, .subject-summary::-webkit-details-marker, .module-summary::-webkit-details-marker { display: none; }
.term-summary h2 { margin: 0; font-family: Georgia, serif; font-size: 1.45rem; }
.term-summary span { color: var(--muted); font-size: .75rem; }
.subject-list { display: grid; gap: .65rem; padding: 0 .65rem .65rem; }
.subject-block { border: 1px solid var(--line); border-radius: 14px; background: var(--paper-2); overflow: clip; }
.subject-block[open] { border-color: var(--line-strong); }
.subject-summary { display: grid; grid-template-columns: 56px 1fr auto; gap: .75rem; align-items: center; padding: .85rem; cursor: pointer; list-style: none; }
.paper-code { color: var(--accent); font-size: .72rem; font-weight: 900; letter-spacing: .04em; }
.subject-summary h3 { margin: 0 0 .18rem; font-size: .95rem; line-height: 1.2; }
.subject-summary small { display: block; color: var(--muted); font-size: .7rem; }
.paper-type { padding: .25rem .45rem; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: .62rem; font-weight: 800; text-transform: uppercase; }
.paper-type.elective { background: var(--gold-soft); color: var(--gold); }
.subject-actions { display: flex; gap: .45rem; padding: 0 .85rem .8rem; }
.small-button { min-height: 36px; padding: .5rem .7rem; border: 1px solid var(--line); border-radius: 10px; background: white; color: var(--accent); font-size: .75rem; font-weight: 800; cursor: pointer; text-decoration: none; }
.module-list { display: grid; gap: .5rem; padding: 0 .55rem .65rem; }
.module-block { border-top: 1px solid #ebe5db; }
.module-summary { display: grid; grid-template-columns: 1fr auto; gap: .5rem; padding: .75rem .3rem; list-style: none; cursor: pointer; }
.module-summary strong { font-size: .83rem; }
.module-summary span { color: var(--muted); font-size: .69rem; }
.topic-list { display: grid; gap: .15rem; padding: 0 0 .45rem; }
.topic-row { display: grid; grid-template-columns: 36px 1fr auto; gap: .55rem; align-items: center; width: 100%; padding: .55rem .25rem; border: 0; border-radius: 8px; background: transparent; text-align: left; cursor: pointer; }
.topic-row:hover, .topic-row:focus-visible { background: var(--accent-soft); outline: none; }
.topic-row .topic-no { color: var(--muted); font-size: .67rem; }
.topic-row strong { font-size: .79rem; font-weight: 650; line-height: 1.3; }
.state-dot { width: 9px; height: 9px; border: 1px solid var(--line-strong); border-radius: 50%; }
.state-dot.ready { background: var(--accent); border-color: var(--accent); }
.state-dot.complete { background: var(--accent-soft); border-color: var(--accent); }
.graph-panel { margin-bottom: 1.2rem; padding: .9rem; border: 1px solid var(--line); border-radius: var(--radius); background: rgba(255,255,255,.62); }
.zoom-controls { display: flex; gap: .35rem; }
.subject-graph-wrap { overflow: auto; min-height: 450px; border: 1px solid var(--line); border-radius: 12px; background: var(--paper-2); touch-action: pan-x pan-y; }
#subjectGraph { display: block; min-width: 1180px; min-height: 620px; }
.graph-edge { fill: none; stroke: #b5ad9f; stroke-width: 1.2; opacity: .78; }
.graph-edge.foundation { stroke: var(--accent-2); stroke-dasharray: 4 4; }
.graph-node rect { fill: white; stroke: var(--line-strong); stroke-width: 1; rx: 10; cursor: pointer; }
.graph-node text { pointer-events: none; fill: var(--ink); font-family: Inter, sans-serif; }
.graph-node .graph-code { fill: var(--accent); font-size: 10px; font-weight: 850; }
.graph-node .graph-title { font-size: 10px; font-weight: 650; }
.graph-node.elective rect { fill: var(--gold-soft); }
.graph-node.selected rect { stroke: var(--accent); stroke-width: 3; }
.graph-node.foundation rect { fill: var(--accent-2-soft); stroke: var(--accent-2); }
.graph-note { margin: .7rem .15rem 0; color: var(--muted); font-size: .73rem; line-height: 1.45; }
.focus-graph { display: grid; gap: .75rem; }
.focus-center { padding: 1rem; border: 2px solid var(--accent); border-radius: 14px; background: var(--accent-soft); }
.focus-center h3 { margin: .2rem 0 .35rem; }
.focus-center p { margin: 0; color: var(--muted); font-size: .8rem; line-height: 1.45; }
.focus-columns { display: grid; gap: .75rem; }
.focus-column { padding: .8rem; border: 1px solid var(--line); border-radius: 14px; background: white; }
.focus-column h4 { margin: 0 0 .6rem; font-size: .8rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
.focus-link { display: grid; grid-template-columns: 1fr auto; gap: .5rem; width: 100%; padding: .55rem 0; border: 0; border-bottom: 1px solid #eee8de; background: transparent; text-align: left; cursor: pointer; }
.focus-link:last-child { border-bottom: 0; }
.focus-link strong { display: block; font-size: .8rem; }
.focus-link small { display: block; margin-top: .12rem; color: var(--muted); font-size: .67rem; }
.source-callout { margin-bottom: 1rem; padding: 1rem; border-left: 4px solid var(--accent-2); border-radius: 0 14px 14px 0; background: var(--accent-2-soft); }
.source-callout p { margin: .35rem 0 0; color: var(--muted); font-size: .82rem; line-height: 1.5; }
.source-register { display: grid; gap: .75rem; }
.source-card { padding: .9rem; border: 1px solid var(--line); border-radius: 14px; background: var(--paper-2); }
.source-card-head { display: grid; grid-template-columns: 58px 1fr; gap: .7rem; }
.source-card h3 { margin: 0; font-size: .95rem; }
.source-card .edition { margin-top: .2rem; color: var(--muted); font-size: .7rem; }
.source-card p { margin: .65rem 0; color: var(--muted); font-size: .78rem; line-height: 1.5; }
.source-actions { display: flex; flex-wrap: wrap; gap: .45rem; }
.warning-badge { display: inline-block; margin-top: .45rem; padding: .28rem .5rem; border-radius: 999px; background: var(--accent-2-soft); color: var(--accent-2); font-size: .66rem; font-weight: 800; }
.bottom-nav { position: fixed; z-index: 50; bottom: 0; left: 0; right: 0; display: grid; grid-template-columns: repeat(4, 1fr); min-height: calc(var(--nav-h) + env(safe-area-inset-bottom)); padding: .35rem .45rem calc(.35rem + env(safe-area-inset-bottom)); border-top: 1px solid var(--line); background: rgba(255,253,248,.96); backdrop-filter: blur(18px); }
.nav-item { display: grid; place-items: center; align-content: center; gap: .16rem; border: 0; border-radius: 12px; background: transparent; color: var(--muted); cursor: pointer; }
.nav-item span:first-child { font-size: 1.15rem; }
.nav-item span:last-child { font-size: .68rem; font-weight: 800; }
.nav-item.active { background: var(--accent-soft); color: var(--accent); }
dialog { color: var(--ink); }
.node-dialog { width: 100%; max-width: none; max-height: 88vh; margin: auto 0 0; padding: .55rem 1rem calc(1.2rem + env(safe-area-inset-bottom)); border: 0; border-radius: 22px 22px 0 0; background: var(--paper-2); box-shadow: var(--shadow); }
.node-dialog::backdrop, .about-dialog::backdrop { background: rgba(25,23,19,.45); backdrop-filter: blur(2px); }
.dialog-handle { width: 42px; height: 4px; margin: 0 auto .8rem; border-radius: 4px; background: var(--line-strong); }
.breadcrumb { align-self: center; color: var(--muted); font-size: .68rem; line-height: 1.4; }
.node-content { padding-top: .75rem; }
.node-kicker { color: var(--accent-2); font-size: .69rem; font-weight: 850; letter-spacing: .1em; text-transform: uppercase; }
.node-content h2 { margin: .3rem 0 .7rem; font-family: Georgia, serif; font-size: 1.8rem; line-height: 1.05; }
.node-content .summary { color: var(--muted); line-height: 1.55; }
.eli15 { margin: 1rem 0; padding: .85rem; border-radius: 12px; background: var(--accent-soft); line-height: 1.5; }
.eli15 strong { display: block; margin-bottom: .25rem; color: var(--accent); font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; }
.node-meta-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: .5rem; margin: 1rem 0; }
.node-meta-grid div { padding: .65rem; border: 1px solid var(--line); border-radius: 10px; }
.node-meta-grid small { display: block; color: var(--muted); font-size: .64rem; text-transform: uppercase; }
.node-meta-grid strong { display: block; margin-top: .15rem; font-size: .78rem; }
.node-section { margin: 1.1rem 0; }
.node-section h3 { margin: 0 0 .55rem; font-size: .8rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
.relation-list { display: grid; gap: .4rem; }
.relation-button { display: grid; grid-template-columns: auto 1fr auto; gap: .55rem; align-items: center; width: 100%; padding: .6rem; border: 1px solid var(--line); border-radius: 10px; background: white; text-align: left; cursor: pointer; }
.relation-button .relation-type { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }
.relation-button.background .relation-type { background: var(--blue); }
.relation-button.related .relation-type { background: var(--gold); }
.relation-button strong { display: block; font-size: .78rem; line-height: 1.3; }
.relation-button small { display: block; margin-top: .12rem; color: var(--muted); font-size: .65rem; }
.law-list { display: flex; flex-wrap: wrap; gap: .4rem; }
.law-pill { padding: .35rem .55rem; border-radius: 999px; background: #ede8df; font-size: .7rem; }
.node-actions { position: sticky; bottom: -.1rem; display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; padding: .75rem 0 .15rem; background: linear-gradient(180deg, rgba(255,253,248,0), var(--paper-2) 22%); }
.node-actions .wide { grid-column: 1 / -1; }
.about-dialog { width: min(calc(100% - 2rem), 520px); padding: 1.1rem; border: 0; border-radius: 18px; background: var(--paper-2); box-shadow: var(--shadow); }
.about-dialog p { color: var(--muted); line-height: 1.55; }
.toast { position: fixed; z-index: 120; left: 50%; bottom: calc(var(--nav-h) + 1rem + env(safe-area-inset-bottom)); transform: translateX(-50%); width: max-content; max-width: calc(100% - 2rem); padding: .7rem .9rem; border-radius: 999px; background: var(--ink); color: white; box-shadow: var(--shadow); font-size: .78rem; }
.empty-state { padding: 1.2rem; border: 1px dashed var(--line-strong); border-radius: 14px; color: var(--muted); text-align: center; line-height: 1.5; }
@media (min-width: 700px) {
  :root { --header-h: 80px; --nav-h: 0px; }
  .site-header { display: grid; grid-template-columns: minmax(210px, 1fr) minmax(360px, 760px) minmax(210px, 1fr); align-items: center; gap: 1rem; padding: .7rem 1.2rem; }
  .brand-row { grid-column: 1; display: flex; justify-content: flex-start; width: 100%; margin: 0; }
  .brand { justify-content: flex-start; }
  .brand-row .icon-button:last-child { margin-left: auto; }
  .search-shell { grid-column: 2; width: 100%; }
  .search-results { grid-column: 2; left: auto; right: auto; top: 100%; width: min(760px, calc(100vw - 2rem)); }
  main { padding-top: 3.7rem; padding-bottom: 3rem; }
  .bottom-nav { position: fixed; top: 73px; right: auto; bottom: auto; left: 50%; z-index: 28; display: flex; justify-content: center; gap: .4rem; min-height: 0; width: max-content; margin: 0; padding: .35rem; border: 1px solid var(--line); border-radius: 999px; background: rgba(255,253,248,.96); box-shadow: 0 8px 24px rgba(35,31,25,.07); transform: translateX(-50%); }
  .nav-item { display: flex; gap: .35rem; min-width: 108px; min-height: 40px; padding: 0 .8rem; border-radius: 999px; }
  .nav-item span:first-child { font-size: .95rem; }
  .nav-item span:last-child { font-size: .74rem; }
  .filter-panel { position: sticky; z-index: 10; top: 145px; float: left; width: 250px; height: calc(100vh - 165px); margin-left: max(1rem, calc((100vw - 1180px)/2)); padding: 1rem; border: 1px solid var(--line); border-radius: var(--radius); box-shadow: none; transform: none; }
  .filter-panel[aria-hidden="true"] { display: none; }
  .filter-panel.open { display: block; }
  .filter-panel .panel-heading .icon-button { display: none; }
  .filter-panel.open ~ main { width: min(calc(100% - 290px), 900px); margin-left: calc(max(1rem, (100vw - 1180px)/2) + 270px); }
  .scrim { display: none !important; }
  .stats-strip { grid-template-columns: repeat(4, 1fr); }
  .card-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .legend-grid { grid-template-columns: repeat(3, 1fr); }
  .legend-grid > div { grid-template-columns: 34px 1fr; }
  .subject-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .focus-columns { grid-template-columns: repeat(3, 1fr); }
  .source-register { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .node-dialog { width: min(720px, calc(100% - 2rem)); max-height: 86vh; margin: auto; padding: 1.1rem; border-radius: 20px; }
  .dialog-handle { display: none; }
  .node-meta-grid { grid-template-columns: repeat(4, 1fr); }
  .node-actions { grid-template-columns: repeat(3, 1fr); }
  .node-actions .wide { grid-column: auto; }
}
@media (min-width: 1020px) {
  .card-list { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .subject-list { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .source-register { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; animation: none !important; transition: none !important; }
}
'''
    (ROOT / 'styles.css').write_text(css, encoding='utf-8')
    js = r'''(() => {
  'use strict';

  const STORAGE_KEY = 'du-llb-graph-v1';
  const REPO_BLOB = 'https://github.com/Legedith/llb/blob/main/';
  const els = {};
  let data;
  let nodes;
  let subjects;
  let subjectMap;
  let searchIndex = [];
  let toastTimer;
  let lastGraphCenteredFocus = null;

  const state = {
    view: 'learn',
    terms: new Set([1, 2, 3, 4, 5, 6]),
    core: true,
    elective: true,
    availableOnly: false,
    bookmarkedOnly: false,
    completed: new Set(),
    bookmarks: new Set(),
    lastNode: null,
    focusNode: null,
    graphScale: 1,
  };

  document.addEventListener('DOMContentLoaded', init);

  async function init() {
    cacheElements();
    bindEvents();
    loadLocalState();
    try {
      const response = await fetch('data/curriculum.json', { cache: 'no-cache' });
      if (!response.ok) throw new Error(`Data request failed: ${response.status}`);
      data = await response.json();
      nodes = data.nodes;
      subjects = data.subjects;
      subjectMap = Object.fromEntries(subjects.map(s => [s.id, s]));
      hydrateNodes();
      buildSearchIndex();
      buildTermFilters();
      chooseInitialFocus();
      renderAll();
      handleHash();
      if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
        navigator.serviceWorker.register('sw.js').catch(() => {});
      }
    } catch (error) {
      console.error(error);
      document.querySelector('main').innerHTML = `<div class="empty-state" style="margin-top:2rem"><strong>The curriculum data could not load.</strong><br>${escapeHtml(error.message)}</div>`;
    }
  }

  function cacheElements() {
    for (const id of [
      'menuButton','filterPanel','closeFilters','panelScrim','aboutButton','aboutDialog','closeAbout',
      'searchForm','searchInput','searchClear','searchResults','termFilters','coreFilter','electiveFilter',
      'availableFilter','bookmarkedFilter','resetFilters','statsStrip','readyList','learningQueue',
      'progressLabel','resumeButton','browseSummary','catalogTree','subjectGraphWrap','subjectGraph',
      'graphSmaller','graphLarger','focusGraph','chooseFocus','sourceRegister','nodeDialog','closeNode',
      'nodeBreadcrumb','nodeContent','toast'
    ]) els[id] = document.getElementById(id);
  }

  function bindEvents() {
    els.menuButton.addEventListener('click', () => toggleFilters(true));
    els.closeFilters.addEventListener('click', () => toggleFilters(false));
    els.panelScrim.addEventListener('click', () => toggleFilters(false));
    els.aboutButton.addEventListener('click', () => els.aboutDialog.showModal());
    els.closeAbout.addEventListener('click', () => els.aboutDialog.close());
    els.closeNode.addEventListener('click', closeNode);
    els.nodeDialog.addEventListener('click', e => {
      if (e.target === els.nodeDialog && window.innerWidth >= 700) closeNode();
    });
    document.querySelectorAll('.nav-item').forEach(button => {
      button.addEventListener('click', () => switchView(button.dataset.target));
    });
    els.searchForm.addEventListener('submit', e => {
      e.preventDefault();
      const first = els.searchResults.querySelector('[data-node-id]');
      if (first) openNode(first.dataset.nodeId);
    });
    els.searchInput.addEventListener('input', debounce(renderSearch, 80));
    els.searchInput.addEventListener('focus', renderSearch);
    els.searchInput.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeSearch();
      if (e.key === 'ArrowDown') {
        const first = els.searchResults.querySelector('[data-node-id]');
        if (first) { e.preventDefault(); first.focus(); }
      }
    });
    els.searchClear.addEventListener('click', () => {
      els.searchInput.value = '';
      closeSearch();
      els.searchInput.focus();
    });
    document.addEventListener('click', e => {
      if (!e.target.closest('.site-header')) closeSearch();
    });
    els.searchResults.addEventListener('click', e => {
      const result = e.target.closest('[data-node-id]');
      if (result) openNode(result.dataset.nodeId);
    });
    els.searchResults.addEventListener('keydown', e => {
      const current = e.target.closest('[data-node-id]');
      if (!current) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const all = [...els.searchResults.querySelectorAll('[data-node-id]')];
        const index = all.indexOf(current);
        const next = e.key === 'ArrowDown' ? all[index + 1] : all[index - 1];
        (next || (e.key === 'ArrowDown' ? all[0] : els.searchInput)).focus();
      }
    });
    for (const [element, key] of [
      [els.coreFilter, 'core'], [els.electiveFilter, 'elective'],
      [els.availableFilter, 'availableOnly'], [els.bookmarkedFilter, 'bookmarkedOnly']
    ]) {
      element.addEventListener('change', () => {
        state[key] = element.checked;
        renderFilteredViews();
        saveLocalState();
      });
    }
    els.resetFilters.addEventListener('click', resetFilters);
    els.readyList.addEventListener('click', openFromEvent);
    els.learningQueue.addEventListener('click', openFromEvent);
    els.catalogTree.addEventListener('click', e => {
      const open = e.target.closest('[data-node-id]');
      if (open && !e.target.closest('summary')) openNode(open.dataset.nodeId);
      const inspect = e.target.closest('[data-inspect]');
      if (inspect) openNode(inspect.dataset.inspect);
    });
    els.catalogTree.addEventListener('toggle', e => {
      const details = e.target;
      if (details.matches('.module-block') && details.open) populateModule(details);
    }, true);
    els.subjectGraph.addEventListener('click', e => {
      const group = e.target.closest('[data-subject-id]');
      if (group) {
        state.focusNode = group.dataset.subjectId;
        renderSubjectGraph();
        renderFocusGraph();
        openNode(group.dataset.subjectId);
      }
    });
    els.subjectGraph.addEventListener('keydown', e => {
      const group = e.target.closest('[data-subject-id]');
      if (group && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault();
        group.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      }
    });
    els.graphSmaller.addEventListener('click', () => adjustGraphScale(-.12));
    els.graphLarger.addEventListener('click', () => adjustGraphScale(.12));
    els.focusGraph.addEventListener('click', openFromEvent);
    els.sourceRegister.addEventListener('click', e => {
      const inspect = e.target.closest('[data-inspect]');
      if (inspect) openNode(inspect.dataset.inspect);
    });
    els.chooseFocus.addEventListener('click', () => {
      els.searchInput.focus();
      els.searchInput.placeholder = 'Choose a node for the focus graph…';
      showToast('Search and open any node; it becomes the graph focus.');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    els.resumeButton.addEventListener('click', () => {
      const id = state.lastNode && nodes?.[state.lastNode] ? state.lastNode : nextIncomplete();
      if (id) openNode(id);
    });
    window.addEventListener('hashchange', handleHash);
    window.addEventListener('keydown', e => {
      if (e.key === '/' && !isTyping()) {
        e.preventDefault();
        els.searchInput.focus();
      }
      if (e.key === 'Escape' && els.nodeDialog.open) closeNode();
    });
    window.matchMedia('(min-width: 700px)').addEventListener('change', setResponsiveFilterState);
  }

  function setResponsiveFilterState() {
    if (window.innerWidth >= 700) {
      els.filterPanel.classList.remove('open');
      els.filterPanel.setAttribute('aria-hidden', 'true');
      els.panelScrim.hidden = true;
      els.menuButton.setAttribute('aria-expanded', 'false');
    } else {
      toggleFilters(false);
    }
  }

  function toggleFilters(open) {
    els.filterPanel.classList.toggle('open', open);
    els.filterPanel.setAttribute('aria-hidden', String(!open));
    els.menuButton.setAttribute('aria-expanded', String(open));
    els.panelScrim.hidden = !open || window.innerWidth >= 700;
    document.body.style.overflow = open && window.innerWidth < 700 ? 'hidden' : '';
  }

  function loadLocalState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      if (Array.isArray(saved.completed)) state.completed = new Set(saved.completed);
      if (Array.isArray(saved.bookmarks)) state.bookmarks = new Set(saved.bookmarks);
      if (Array.isArray(saved.terms)) state.terms = new Set(saved.terms.map(Number));
      for (const key of ['core','elective','availableOnly','bookmarkedOnly']) {
        if (typeof saved[key] === 'boolean') state[key] = saved[key];
      }
      if (typeof saved.lastNode === 'string') state.lastNode = saved.lastNode;
      if (typeof saved.focusNode === 'string') state.focusNode = saved.focusNode;
      if (typeof saved.graphScale === 'number') state.graphScale = clamp(saved.graphScale, .65, 1.55);
    } catch (_) {}
  }

  function saveLocalState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      completed: [...state.completed], bookmarks: [...state.bookmarks], terms: [...state.terms],
      core: state.core, elective: state.elective, availableOnly: state.availableOnly,
      bookmarkedOnly: state.bookmarkedOnly, lastNode: state.lastNode, focusNode: state.focusNode,
      graphScale: state.graphScale,
    }));
  }

  function hydrateNodes() {
    for (const subject of subjects) {
      const node = nodes[subject.id] || (nodes[subject.id] = {});
      Object.assign(node, subject);
    }
    for (const node of Object.values(nodes)) {
      if (node.subjectId) {
        const subject = subjectMap[node.subjectId];
        if (!subject) continue;
        node.subjectCode = subject.code;
        node.subjectTitle = subject.title;
        node.term = subject.term;
        node.elective = subject.elective;
        node.category = subject.category;
        node.source = subject.source;
        node.sourceStatus = subject.sourceStatus;
        node.sourceNote = subject.sourceNote;
        node.edition = subject.edition;
        node.laws = subject.laws;
        if (node.moduleId && nodes[node.moduleId]) node.moduleTitle = nodes[node.moduleId].title;
      }
      if (!node.breadcrumb) {
        if (node.subjectId) {
          node.breadcrumb = [`Term ${node.term}`, node.subjectTitle];
          if (node.moduleTitle) node.breadcrumb.push(node.moduleTitle);
          if (node.kind === 'topic') node.breadcrumb.push(node.title);
        } else if (node.kind === 'subject') {
          node.breadcrumb = [`Term ${node.term}`, node.title];
        } else {
          node.breadcrumb = ['Foundation', node.title];
        }
      }
    }
  }

  function buildSearchIndex() {
    searchIndex = Object.values(nodes).map(node => {
      const subject = node.subjectId ? subjectMap[node.subjectId] : null;
      const text = [
        node.id, node.title, node.kind, node.summary, node.eli15, node.subjectCode, node.subjectTitle,
        node.moduleTitle, node.category, ...(node.tags || []), ...(node.laws || []),
        ...(node.aliases || []), ...(subject?.aliases || []), subject?.catalogCode,
      ].filter(Boolean).join(' ').toLowerCase();
      return { id: node.id, text, title: node.title.toLowerCase(), code: (node.code || node.subjectCode || '').toLowerCase() };
    });
  }

  function buildTermFilters() {
    els.termFilters.innerHTML = [1,2,3,4,5,6].map(term =>
      `<button type="button" class="filter-chip ${state.terms.has(term) ? 'active' : ''}" data-term="${term}" aria-pressed="${state.terms.has(term)}">Term ${term}</button>`
    ).join('');
    els.termFilters.addEventListener('click', e => {
      const button = e.target.closest('[data-term]');
      if (!button) return;
      const term = Number(button.dataset.term);
      state.terms.has(term) ? state.terms.delete(term) : state.terms.add(term);
      button.classList.toggle('active', state.terms.has(term));
      button.setAttribute('aria-pressed', String(state.terms.has(term)));
      renderFilteredViews();
      saveLocalState();
    });
    syncFilterInputs();
  }

  function syncFilterInputs() {
    els.coreFilter.checked = state.core;
    els.electiveFilter.checked = state.elective;
    els.availableFilter.checked = state.availableOnly;
    els.bookmarkedFilter.checked = state.bookmarkedOnly;
  }

  function resetFilters() {
    state.terms = new Set([1,2,3,4,5,6]);
    state.core = true; state.elective = true; state.availableOnly = false; state.bookmarkedOnly = false;
    buildTermFilters();
    renderFilteredViews();
    saveLocalState();
  }

  function chooseInitialFocus() {
    if (!state.focusNode || !nodes[state.focusNode]) state.focusNode = nextIncomplete() || 'f01';
  }

  function renderAll() {
    renderStats();
    renderLearn();
    renderBrowse();
    renderSubjectGraph();
    renderFocusGraph();
    renderSources();
    switchView(state.view, false);
    setResponsiveFilterState();
  }

  function renderFilteredViews() {
    renderLearn();
    renderBrowse();
    renderSources();
  }

  function renderStats() {
    const s = data.meta.stats;
    els.statsStrip.innerHTML = [
      [s.subjects, 'papers'], [s.modules, 'modules'], [s.topics, 'topic nodes'], [s.strictEdges, 'strict edges']
    ].map(([value, label]) => `<div class="stat"><strong>${formatNumber(value)}</strong><span>${label}</span></div>`).join('');
  }

  function renderLearn() {
    const ready = data.learningOrder.filter(id => isAvailable(id) && isNodeVisible(nodes[id])).slice(0, 9);
    els.readyList.innerHTML = ready.length ? ready.map((id, index) => nodeCard(nodes[id], index + 1)).join('') :
      `<div class="empty-state">No visible node is ready under the current filters. Broaden the filters or inspect the next locked node in the queue.</div>`;

    const queue = data.learningOrder.filter(id => !state.completed.has(id) && isNodeVisible(nodes[id])).slice(0, 24);
    els.learningQueue.innerHTML = queue.length ? queue.map((id, index) => timelineRow(nodes[id], index + 1)).join('') :
      `<div class="empty-state">Every visible learnable node is marked complete.</div>`;
    const completed = [...state.completed].filter(id => nodes[id]?.learnable).length;
    const total = data.meta.stats.learnableNodes;
    els.progressLabel.textContent = `${formatNumber(completed)} / ${formatNumber(total)} complete`;
  }

  function nodeCard(node, ordinal) {
    const ready = isAvailable(node.id);
    const code = node.subjectCode || (node.term === 0 ? 'METHOD' : node.id.toUpperCase());
    return `<button class="node-card ${state.completed.has(node.id) ? 'complete' : ''}" type="button" data-node-id="${node.id}">
      <span class="ordinal">${ready ? 'READY' : String(ordinal).padStart(2, '0')}</span>
      <span class="node-main"><span class="eyebrow">${escapeHtml(code)} · ${escapeHtml(kindLabel(node))}</span><h3>${escapeHtml(node.title)}</h3><p>${escapeHtml(node.eli15 || node.summary || '')}</p>
      <span class="meta"><span>${node.term ? `Term ${node.term}` : 'Foundation'}</span><span>${node.prerequisites?.length || 0} prerequisites</span><span>${node.unlocks?.length || 0} unlocks</span></span></span>
      <span class="arrow" aria-hidden="true">›</span></button>`;
  }

  function timelineRow(node, ordinal) {
    const ready = isAvailable(node.id);
    const complete = state.completed.has(node.id);
    const stateClass = complete ? 'complete' : ready ? 'ready' : 'locked';
    const code = node.subjectCode || 'METHOD';
    const prereqText = ready ? 'Ready now' : `${countMissingPrerequisites(node.id)} prerequisite${countMissingPrerequisites(node.id) === 1 ? '' : 's'} not complete`;
    return `<button class="timeline-row ${stateClass}" type="button" data-node-id="${node.id}"><span class="timeline-dot">${complete ? '✓' : ordinal}</span><span class="timeline-copy"><strong>${escapeHtml(node.title)}</strong><small>${escapeHtml(code)} · ${escapeHtml(prereqText)}</small></span></button>`;
  }

  function renderBrowse() {
    const visible = subjects.filter(subjectVisible);
    const coreCount = visible.filter(s => !s.elective).length;
    const electiveCount = visible.filter(s => s.elective).length;
    els.browseSummary.innerHTML = `<span class="summary-pill">${visible.length} papers</span><span class="summary-pill">${coreCount} core</span><span class="summary-pill">${electiveCount} elective</span><span class="summary-pill">topics render when opened</span>`;

    const terms = [1,2,3,4,5,6].filter(term => state.terms.has(term));
    els.catalogTree.innerHTML = terms.map(term => {
      const termSubjects = visible.filter(s => s.term === term);
      if (!termSubjects.length) return '';
      return `<details class="term-block" ${term === 1 ? 'open' : ''}>
        <summary class="term-summary"><h2>Term ${term}</h2><span>${termSubjects.length} paper${termSubjects.length === 1 ? '' : 's'} · ${formatNumber(termSubjects.reduce((n,s)=>n+s.topicCount,0))} nodes</span></summary>
        <div class="subject-list">${termSubjects.map(subjectBlock).join('')}</div>
      </details>`;
    }).join('') || `<div class="empty-state">No papers match the filters.</div>`;
  }

  function subjectBlock(subject) {
    const warning = subject.sourceNote ? ' · source note' : '';
    return `<details class="subject-block" data-subject="${subject.id}">
      <summary class="subject-summary"><span class="paper-code">${escapeHtml(subject.code)}</span><span><h3>${escapeHtml(subject.title)}</h3><small>${subject.moduleCount} modules · ${subject.topicCount} nodes${warning}</small></span><span class="paper-type ${subject.elective ? 'elective' : ''}">${subject.elective ? 'Elective' : 'Core'}</span></summary>
      <div class="subject-actions"><button class="small-button" type="button" data-inspect="${subject.id}">Inspect paper</button><a class="small-button" href="${escapeAttr(subject.notePath)}">Note scaffold</a></div>
      <div class="module-list">${subject.moduleIds.map(mid => moduleBlock(nodes[mid])).join('')}</div>
    </details>`;
  }

  function moduleBlock(module) {
    return `<details class="module-block" data-module-id="${module.id}"><summary class="module-summary"><strong>${module.moduleNumber}. ${escapeHtml(module.title)}</strong><span>${module.children.length} nodes</span></summary><div class="topic-list" data-topic-container="${module.id}"></div></details>`;
  }

  function populateModule(details) {
    const mid = details.dataset.moduleId;
    const container = details.querySelector('[data-topic-container]');
    if (!mid || !container || container.dataset.loaded) return;
    const module = nodes[mid];
    container.innerHTML = module.children.filter(id => isNodeVisible(nodes[id])).map(id => {
      const node = nodes[id];
      const status = state.completed.has(id) ? 'complete' : isAvailable(id) ? 'ready' : '';
      return `<button class="topic-row" type="button" data-node-id="${id}"><span class="topic-no">${module.moduleNumber}.${node.topicNumber}</span><strong>${escapeHtml(node.title)}</strong><span class="state-dot ${status}" aria-label="${status || 'locked'}"></span></button>`;
    }).join('') || `<div class="empty-state">No topic matches the current filters.</div>`;
    container.dataset.loaded = 'true';
  }

  function renderSubjectGraph() {
    const svg = els.subjectGraph;
    if (!data) return;
    const scale = state.graphScale;
    const compact = window.innerWidth >= 1100;
    const nodeW = compact ? 138 : 178;
    const nodeH = 52;
    const colGap = compact ? 154 : 228;
    const rowGap = 78;
    const firstColumnX = compact ? 156 : 240;
    const positions = { 'foundation-spine': { x: compact ? 8 : 25, y: 370 } };
    const byTerm = new Map([1,2,3,4,5,6].map(t => [t, subjects.filter(s => s.term === t)]));
    let maxRows = 0;
    for (const [term, list] of byTerm) {
      maxRows = Math.max(maxRows, list.length);
      list.forEach((s, index) => positions[s.id] = { x: firstColumnX + (term - 1) * colGap, y: 45 + index * rowGap });
    }
    const width = firstColumnX + 5 * colGap + nodeW + (compact ? 18 : 55);
    const height = Math.max(670, 65 + maxRows * rowGap);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.style.width = `${width * scale}px`;
    svg.style.height = `${height * scale}px`;
    svg.innerHTML = `<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#aaa08f"></path></marker></defs><title id="subjectGraphTitle">DU LL.B. subject prerequisite graph</title><desc id="subjectGraphDesc">Forty-five papers in six term columns, with strict prerequisite arrows.</desc>`;

    for (const edge of data.subjectEdges) {
      const a = positions[edge.from], b = positions[edge.to];
      if (!a || !b) continue;
      const startX = edge.from === 'foundation-spine' ? a.x + nodeW : a.x + nodeW;
      const startY = a.y + nodeH / 2;
      const endX = b.x;
      const endY = b.y + nodeH / 2;
      const sameCol = Math.abs(startX - endX) < nodeW;
      const curve = sameCol ? 70 : Math.max(38, (endX - startX) * .42);
      const d = sameCol
        ? `M ${startX} ${startY} C ${startX + curve} ${startY}, ${endX + curve} ${endY}, ${endX} ${endY}`
        : `M ${startX} ${startY} C ${startX + curve} ${startY}, ${endX - curve} ${endY}, ${endX} ${endY}`;
      svg.insertAdjacentHTML('beforeend', `<path class="graph-edge ${edge.from === 'foundation-spine' ? 'foundation' : ''}" d="${d}" marker-end="url(#arrow)"></path>`);
    }

    svg.insertAdjacentHTML('beforeend', graphNodeSvg({ id: 'foundation-spine', code: 'METHOD', title: '26-node legal-method spine', elective: false }, positions['foundation-spine'], true, nodeW));
    for (const subject of subjects) svg.insertAdjacentHTML('beforeend', graphNodeSvg(subject, positions[subject.id], false, nodeW));
    const focused = nodes[state.focusNode];
    const focusSubjectId = focused?.kind === 'subject' ? focused.id : focused?.subjectId;
    if (focusSubjectId && positions[focusSubjectId] && lastGraphCenteredFocus !== focusSubjectId) {
      lastGraphCenteredFocus = focusSubjectId;
      requestAnimationFrame(() => {
        const target = positions[focusSubjectId].x * scale - (els.subjectGraphWrap.clientWidth - nodeW * scale) / 2;
        els.subjectGraphWrap.scrollLeft = Math.max(0, target);
      });
    }
  }

  function graphNodeSvg(subject, pos, foundation, nodeW) {
    const focused = nodes[state.focusNode];
    const focusSubjectId = focused?.kind === 'subject' ? focused.id : focused?.subjectId;
    const selected = focusSubjectId === subject.id;
    const words = wrapText(subject.title, Math.max(17, Math.floor(nodeW / 7))).slice(0, 2);
    const titleLines = words.map((line, i) => `<text class="graph-title" x="10" y="${31 + i * 12}">${escapeXml(line)}</text>`).join('');
    return `<g class="graph-node ${subject.elective ? 'elective' : ''} ${foundation ? 'foundation' : ''} ${selected ? 'selected' : ''}" transform="translate(${pos.x} ${pos.y})" ${foundation ? '' : `data-subject-id="${subject.id}"`} tabindex="${foundation ? '-1' : '0'}" role="button" aria-label="${escapeAttr(subject.code + ' ' + subject.title)}"><rect width="${nodeW}" height="52"></rect><text class="graph-code" x="10" y="15">${escapeXml(subject.code)}</text>${titleLines}</g>`;
  }

  function renderFocusGraph() {
    const node = nodes[state.focusNode] || nodes[nextIncomplete()] || nodes.f01;
    if (!node) return;
    const prereqs = node.prerequisites || [];
    const unlocks = node.unlocks || [];
    const context = [];
    if (node.kind === 'subject') {
      for (const id of node.background || []) context.push([id, 'Background']);
      for (const id of node.related || []) context.push([id, 'Related']);
    }
    els.focusGraph.innerHTML = `<div class="focus-center"><span class="eyebrow">${escapeHtml(node.subjectCode || node.code || kindLabel(node))}</span><h3>${escapeHtml(node.title)}</h3><p>${escapeHtml(node.summary || '')}</p></div>
      <div class="focus-columns">
        ${focusColumn('Prerequisites', prereqs, 'Nothing is required before this node.')}
        ${focusColumn('Unlocks', unlocks.slice(0, 18), 'No direct unlocks recorded.')}
        ${focusContextColumn(context)}
      </div>`;
  }

  function focusColumn(title, ids, empty) {
    return `<div class="focus-column"><h4>${title}</h4>${ids.length ? ids.map(id => focusLink(id)).join('') : `<p class="quiet-label">${empty}</p>`}</div>`;
  }

  function focusContextColumn(context) {
    return `<div class="focus-column"><h4>Context links</h4>${context.length ? context.map(([id,type]) => focusLink(id, type)).join('') : `<p class="quiet-label">Open a subject node to see optional background and related papers.</p>`}</div>`;
  }

  function focusLink(id, type = '') {
    const node = nodes[id];
    if (!node) return '';
    return `<button class="focus-link" type="button" data-node-id="${id}"><span><strong>${escapeHtml(node.title)}</strong><small>${escapeHtml(node.subjectCode || node.code || kindLabel(node))}${type ? ` · ${type}` : ''}</small></span><span aria-hidden="true">›</span></button>`;
  }

  function adjustGraphScale(delta) {
    state.graphScale = clamp(state.graphScale + delta, .65, 1.55);
    saveLocalState();
    renderSubjectGraph();
  }

  function renderSources() {
    const visible = subjects.filter(subjectVisible);
    els.sourceRegister.innerHTML = visible.map(subject => {
      const warning = subject.sourceNote ? `<span class="warning-badge">Edition / source note</span>` : '';
      return `<article class="source-card"><div class="source-card-head"><span class="paper-code">${escapeHtml(subject.code)}</span><div><h3>${escapeHtml(subject.title)}</h3><div class="edition">Term ${subject.term} · ${subject.elective ? 'Elective' : 'Core'} · ${escapeHtml(subject.edition || 'Edition not stated')}</div>${warning}</div></div>
        <p>${escapeHtml(subject.sourceNote || 'Official DU course material; verify present law before relying on substantive propositions.')}</p>
        <div class="source-actions"><a class="small-button" href="${escapeAttr(subject.source)}" target="_blank" rel="noopener">Open DU source</a><button class="small-button" type="button" data-inspect="${subject.id}">Inspect nodes</button><a class="small-button" href="${escapeAttr(subject.notePath)}">Note scaffold</a></div></article>`;
    }).join('') || `<div class="empty-state">No source matches the filters.</div>`;
  }

  function switchView(view, scroll = true) {
    if (!['learn','browse','graph','sources'].includes(view)) view = 'learn';
    state.view = view;
    document.querySelectorAll('.view').forEach(section => {
      const active = section.dataset.view === view;
      section.hidden = !active;
      section.classList.toggle('active', active);
    });
    document.querySelectorAll('.nav-item').forEach(button => {
      const active = button.dataset.target === view;
      button.classList.toggle('active', active);
      active ? button.setAttribute('aria-current', 'page') : button.removeAttribute('aria-current');
    });
    if (view === 'graph') { renderSubjectGraph(); renderFocusGraph(); }
    if (scroll) window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function renderSearch() {
    if (!data) return;
    const query = normalize(els.searchInput.value);
    els.searchClear.hidden = !query;
    if (query.length < 2) { closeSearch(); return; }
    const terms = query.split(/\s+/).filter(Boolean);
    const results = searchIndex.map(entry => {
      if (!terms.every(term => entry.text.includes(term))) return null;
      let score = 0;
      if (entry.title === query) score += 100;
      if (entry.title.startsWith(query)) score += 55;
      if (entry.code === query || entry.id === query) score += 90;
      if (entry.code.startsWith(query)) score += 35;
      score += terms.reduce((sum, term) => sum + (entry.title.includes(term) ? 12 : 2), 0);
      const node = nodes[entry.id];
      if (node.kind === 'subject') score += 8;
      if (state.bookmarks.has(entry.id)) score += 4;
      return { id: entry.id, score };
    }).filter(Boolean).sort((a,b) => b.score - a.score || nodeSort(nodes[a.id], nodes[b.id])).slice(0, 30);

    els.searchResults.innerHTML = results.length ? results.map(({id}) => searchResult(nodes[id])).join('') : `<div class="empty-state">No node matches “${escapeHtml(els.searchInput.value)}”.</div>`;
    els.searchResults.hidden = false;
  }

  function searchResult(node) {
    const code = node.code || node.subjectCode || (node.term === 0 ? 'METHOD' : node.id);
    const context = node.moduleTitle ? `${node.subjectTitle} › ${node.moduleTitle}` : node.subjectTitle || node.summary || '';
    return `<button class="search-result" type="button" data-node-id="${node.id}"><span class="code">${escapeHtml(code)}</span><span><strong>${escapeHtml(node.title)}</strong><small>${escapeHtml(context)}</small></span><span class="kind">${escapeHtml(kindLabel(node))}</span></button>`;
  }

  function closeSearch() {
    els.searchResults.hidden = true;
    els.searchResults.innerHTML = '';
    els.searchClear.hidden = !els.searchInput.value;
  }

  function openFromEvent(e) {
    const target = e.target.closest('[data-node-id]');
    if (target) openNode(target.dataset.nodeId);
  }

  function openNode(id, updateHash = true) {
    const node = nodes?.[id];
    if (!node) return;
    state.lastNode = id;
    state.focusNode = id;
    saveLocalState();
    els.nodeBreadcrumb.textContent = (node.breadcrumb || [node.title]).join(' › ');
    els.nodeContent.innerHTML = renderNodeContent(node);
    bindNodeDialogActions(node);
    if (!els.nodeDialog.open) els.nodeDialog.showModal();
    if (updateHash) { try { history.replaceState(null, '', `#node=${encodeURIComponent(id)}`); } catch (_) {} }
    renderFocusGraph();
    renderSubjectGraph();
    closeSearch();
  }

  function closeNode() {
    if (els.nodeDialog.open) els.nodeDialog.close();
    if (location.hash.startsWith('#node=')) {
      try { history.replaceState(null, '', location.pathname + location.search); } catch (_) { try { location.hash = ''; } catch (_) {} }
    }
  }

  function renderNodeContent(node) {
    const code = node.code || node.subjectCode || (node.term === 0 ? 'METHOD' : node.id.toUpperCase());
    const ready = node.learnable ? isAvailable(node.id) : true;
    const status = node.learnable ? state.completed.has(node.id) ? 'Complete' : ready ? 'Ready' : 'Locked' : 'Container';
    const prereqs = relationSection('Strict prerequisites', node.prerequisites || [], 'strict', 'This node has no strict prerequisite.');
    const unlocks = relationSection('Direct unlocks', node.unlocks || [], 'strict', 'No direct unlock is recorded.');
    let context = '';
    if (node.kind === 'subject') {
      context += relationSection('Helpful background', node.background || [], 'background', 'No optional background link recorded.');
      context += relationSection('Related papers', node.related || [], 'related', 'No related paper link recorded.');
    }
    let children = '';
    if (node.kind === 'subject') {
      children = `<section class="node-section"><h3>Modules</h3><div class="relation-list">${node.moduleIds.map(mid => relationButton(mid, 'related')).join('')}</div></section>`;
    } else if (node.kind === 'module') {
      children = `<section class="node-section"><h3>Topic nodes</h3><div class="relation-list">${node.children.map(id => relationButton(id, 'related')).join('')}</div></section>`;
    }
    const laws = (node.laws || []).length ? `<section class="node-section"><h3>Principal legislation / instruments</h3><div class="law-list">${node.laws.map(law => `<span class="law-pill">${escapeHtml(law)}</span>`).join('')}</div></section>` : '';
    const sourceNote = node.sourceNote ? `<div class="source-callout"><strong>Source note</strong><p>${escapeHtml(node.sourceNote)}</p></div>` : '';
    const eli = node.eli15 ? `<div class="eli15"><strong>ELI15</strong>${escapeHtml(node.eli15)}</div>` : '';
    const noteHref = node.notePath || (node.subjectId ? subjectMap[node.subjectId]?.notePath : 'notes/foundations.md');
    const githubHref = REPO_BLOB + noteHref;
    const completeLabel = state.completed.has(node.id) ? 'Mark incomplete' : ready ? 'Mark complete' : 'Mark complete anyway';
    const bookmarkLabel = state.bookmarks.has(node.id) ? 'Remove bookmark' : 'Bookmark';
    const actions = `<div class="node-actions">
      ${node.learnable ? `<button id="completeNodeAction" class="button" type="button">${completeLabel}</button>` : ''}
      <button id="bookmarkNodeAction" class="button secondary" type="button">${bookmarkLabel}</button>
      <button id="focusNodeAction" class="button secondary ${node.learnable ? '' : 'wide'}" type="button">Focus in graph</button>
      <a class="button secondary" href="${escapeAttr(githubHref)}" target="_blank" rel="noopener">Open note on GitHub</a>
      ${node.source ? `<a class="button secondary" href="${escapeAttr(node.source)}" target="_blank" rel="noopener">Open DU source</a>` : ''}
    </div>`;
    return `<span class="node-kicker">${escapeHtml(code)} · ${escapeHtml(kindLabel(node))}</span><h2>${escapeHtml(node.title)}</h2><p class="summary">${escapeHtml(node.summary || '')}</p>${eli}
      <div class="node-meta-grid"><div><small>Status</small><strong>${status}</strong></div><div><small>Term</small><strong>${node.term || 'Method spine'}</strong></div><div><small>Edition</small><strong>${escapeHtml(node.edition || 'Method node')}</strong></div><div><small>Stable ID</small><strong>${escapeHtml(node.id)}</strong></div></div>
      ${sourceNote}${prereqs}${unlocks}${context}${children}${laws}${actions}`;
  }

  function relationSection(title, ids, type, empty) {
    return `<section class="node-section"><h3>${title}</h3>${ids.length ? `<div class="relation-list">${ids.slice(0, 80).map(id => relationButton(id, type)).join('')}</div>` : `<p class="quiet-label">${empty}</p>`}</section>`;
  }

  function relationButton(id, type) {
    const node = nodes[id];
    if (!node) return '';
    const code = node.code || node.subjectCode || (node.term === 0 ? 'METHOD' : kindLabel(node));
    return `<button class="relation-button ${type}" type="button" data-relation-node="${id}"><span class="relation-type"></span><span><strong>${escapeHtml(node.title)}</strong><small>${escapeHtml(code)}</small></span><span aria-hidden="true">›</span></button>`;
  }

  function bindNodeDialogActions(node) {
    els.nodeContent.querySelectorAll('[data-relation-node]').forEach(button => button.addEventListener('click', () => openNode(button.dataset.relationNode)));
    const complete = document.getElementById('completeNodeAction');
    if (complete) complete.addEventListener('click', () => toggleComplete(node.id));
    document.getElementById('bookmarkNodeAction')?.addEventListener('click', () => toggleBookmark(node.id));
    document.getElementById('focusNodeAction')?.addEventListener('click', () => {
      state.focusNode = node.id;
      saveLocalState();
      closeNode();
      switchView('graph');
      renderFocusGraph();
      renderSubjectGraph();
    });
  }

  function toggleComplete(id) {
    const wasComplete = state.completed.has(id);
    wasComplete ? state.completed.delete(id) : state.completed.add(id);
    saveLocalState();
    renderLearn(); renderBrowse(); renderFocusGraph();
    openNode(id, false);
    showToast(wasComplete ? 'Node marked incomplete.' : `Complete. ${nodes[id].unlocks?.filter(n => isAvailable(n)).length || 0} direct node(s) now ready.`);
  }

  function toggleBookmark(id) {
    const had = state.bookmarks.has(id);
    had ? state.bookmarks.delete(id) : state.bookmarks.add(id);
    saveLocalState();
    renderFilteredViews();
    openNode(id, false);
    showToast(had ? 'Bookmark removed.' : 'Node bookmarked.');
  }

  function handleHash() {
    if (!data) return;
    const match = location.hash.match(/^#node=(.+)$/);
    if (match) {
      const id = decodeURIComponent(match[1]);
      if (nodes[id]) openNode(id, false);
    }
  }

  function isAvailable(id) {
    const node = nodes[id];
    return Boolean(node?.learnable && !state.completed.has(id) && (node.prerequisites || []).every(pre => state.completed.has(pre)));
  }

  function countMissingPrerequisites(id) {
    return (nodes[id]?.prerequisites || []).filter(pre => !state.completed.has(pre)).length;
  }

  function nextIncomplete() {
    return data?.learningOrder.find(id => !state.completed.has(id)) || null;
  }

  function isNodeVisible(node) {
    if (!node) return false;
    if (node.term && !state.terms.has(node.term)) return false;
    if (node.term && node.elective && !state.elective) return false;
    if (node.term && !node.elective && !state.core) return false;
    if (state.availableOnly && node.learnable && !isAvailable(node.id)) return false;
    if (state.bookmarkedOnly && !state.bookmarks.has(node.id) && !state.bookmarks.has(node.subjectId)) return false;
    return true;
  }

  function subjectVisible(subject) {
    if (!state.terms.has(subject.term)) return false;
    if (subject.elective && !state.elective) return false;
    if (!subject.elective && !state.core) return false;
    if (state.bookmarkedOnly && !state.bookmarks.has(subject.id) && !subject.moduleIds.some(mid => state.bookmarks.has(mid) || nodes[mid].children.some(id => state.bookmarks.has(id)))) return false;
    if (state.availableOnly && !isAvailable(subject.firstNode) && !subject.moduleIds.some(mid => nodes[mid].children.some(id => isAvailable(id)))) return false;
    return true;
  }

  function kindLabel(node) {
    if (node.kind === 'topic') return 'Topic';
    if (node.kind === 'module') return 'Module';
    if (node.kind === 'subject') return node.elective ? 'Elective paper' : 'Core paper';
    if (node.kind === 'skill') return 'Method skill';
    return 'Foundation';
  }

  function nodeSort(a, b) {
    return (a.term || 0) - (b.term || 0) || (a.learningOrder || 999999) - (b.learningOrder || 999999) || a.title.localeCompare(b.title);
  }

  function showToast(message) {
    clearTimeout(toastTimer);
    els.toast.textContent = message;
    els.toast.hidden = false;
    toastTimer = setTimeout(() => { els.toast.hidden = true; }, 2600);
  }

  function wrapText(value, limit) {
    const words = value.split(/\s+/); const lines = []; let line = '';
    for (const word of words) {
      const next = line ? `${line} ${word}` : word;
      if (next.length > limit && line) { lines.push(line); line = word; } else line = next;
    }
    if (line) lines.push(line);
    return lines;
  }

  function normalize(value) { return String(value || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').trim(); }
  function escapeHtml(value) { return String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch])); }
  function escapeAttr(value) { return escapeHtml(value); }
  function escapeXml(value) { return escapeHtml(value); }
  function formatNumber(value) { return new Intl.NumberFormat('en-IN').format(value); }
  function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }
  function debounce(fn, wait) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); }; }
  function isTyping() { const tag = document.activeElement?.tagName; return tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable; }
})();
'''
    (ROOT / 'app.js').write_text(js, encoding='utf-8')

    manifest = {
        'name': 'DU LL.B. Knowledge Graph',
        'short_name': 'LL.B. Graph',
        'description': 'Mobile-first prerequisite graph and note index for DU LL.B. course materials.',
        'start_url': './',
        'display': 'standalone',
        'background_color': '#f6f1e7',
        'theme_color': '#f6f1e7',
        'icons': [{'src': 'assets/icon.svg', 'sizes': 'any', 'type': 'image/svg+xml', 'purpose': 'any maskable'}],
    }
    (ROOT / 'manifest.webmanifest').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    icon = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="LL.B. Knowledge Graph icon"><rect width="512" height="512" rx="112" fill="#f6f1e7"/><circle cx="256" cy="256" r="164" fill="#dfeae3" stroke="#274c3b" stroke-width="18"/><text x="256" y="337" text-anchor="middle" font-family="Georgia,serif" font-size="260" fill="#274c3b">§</text></svg>'''
    (ROOT / 'assets' / 'icon.svg').write_text(icon, encoding='utf-8')

    sw = '''const CACHE = 'du-llb-graph-v2';
const CORE = ['./', 'index.html', 'styles.css', 'app.js', 'data/curriculum.json', 'manifest.webmanifest', 'assets/icon.svg'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(CORE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then(cache => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(event.request);
        if (cached) return cached;
        if (event.request.mode === 'navigate') return caches.match('./index.html');
        return Response.error();
      })
  );
});
'''
    (ROOT / 'sw.js').write_text(sw, encoding='utf-8')
    (ROOT / '.nojekyll').write_text('', encoding='utf-8')
    (ROOT / '404.html').write_text(index_html.replace('<title>DU LL.B. Knowledge Graph</title>', '<title>Page not found · DU LL.B. Knowledge Graph</title>'), encoding='utf-8')


def main() -> None:
    clean_root()
    data, nodes, topo, validation = build_graph()
    write_data(data)
    generate_notes(data, nodes)
    generate_subject_indexes(data, nodes)
    generate_docs(data, validation, nodes)
    generate_web_assets()
    files = [p for p in ROOT.rglob('*') if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print(json.dumps({
        'root': str(ROOT),
        'files': len(files),
        'bytes': total,
        'stats': data['meta']['stats'],
        'firstLearningNodes': topo[:12],
        'lastLearningNodes': topo[-5:],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
