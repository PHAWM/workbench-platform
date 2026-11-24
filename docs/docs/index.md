# PHAWM: Participatory AI Auditing Workbench

<img src="/media/phawm_Workbench.png" alt="Sample Image" width="600" style="display: block; margin: 0 auto">

*The PHAWM Workbench enables participatory AI auditing through a structured four-phase process where auditors can understand, define, evaluate, and inform AI applications.*

## Overview

The Participatory Harms Audit Workbench for Machine Learning (PHAWM) is a comprehensive platform that enables **participatory AI auditing** by empowering end-users and decision-subjects without AI development expertise to conduct systematic, independent audits of AI applications.

## Key Aims

PHAWM supports participatory AI auditing:

- **Where AI end-users or decision-subjects are without AI development expertise** ("auditors") 
- **Carry out a systematic, independent and documented process** for obtaining audit evidence and evaluating it objectively to determine the extent to which the audit criteria are fulfilled (an "audit")
- Of an **AI application** (a solution to fulfill a specific purpose)
- For an **organisation that is interested in the audit results** (the "audit instigator")

### Core Features

- **Universal Platform**: Works for both predictive and generative AI applications
- **Modular Tools**: Provides tools that integrate with the workbench to assist with auditing, including synthetic data creation, instance-specific feedback through markup, and reporting capabilities
- **Multiple Audit Pathways**: Supports opaque-box, translucent-box, and transparent-box auditing approaches

## System Architecture

### Roles and Responsibilities

**Audit Instigator**
- Sets up audits with relevant AI application information
- May not be identical to the AI Operator who developed the application
- Provides access to models/data through API calls when available
- Receives audit results and feedback

**Auditors**
- Non-technical end-users or decision-subjects
- Invited by audit instigators (directly or via invitation links)
- Can participate in multiple audits
- Defines audit criteria and conducts performance analyses
- Provides final audit assessments

## Auditing Process

The PHAWM process follows a structured four-phase approach inspired by Birhane 2024's framework:

### 1. Auditor UNDERSTANDS AI Application
- Reviews AI application overview provided by audit instigator
- Accesses lay-user friendly descriptions of the model and its purpose
- Understands input data requirements and legal frameworks

### 2. Auditor DEFINES Audit Criteria
- Creates new audit criteria or selects from existing criteria
- Defines Events (potential harms or benefits) with:
  - Name and valence (positive/negative)
  - Likelihood and magnitude scores
  - Cause identification (optional)
  - Categories from taxonomy
  - Entities impacted
- Associates Metrics with Events to create measurable criteria

### 3. Auditor EVALUATES Risk and Performance
- Assesses performance against each Event|Metric pair
- Conducts outcome evaluation when model access is available
- Enters Pass, Fail, or Inconclusive assessments
- Provides interpretation notes for each criterion

### 4. Audit Insights INFORM Audit Operator
- Reviews audit overview and results
- Provides final overall assessment (Pass/Fail/Inconclusive)
- Submits structured feedback to audit instigator

## Audit Setup Requirements

### Information Provided by Audit Instigator

**AI Application Details** (based on model cards, targeted at non-technical audience):
- Purpose and intended use of the AI application
- Developer information
- Target user groups
- Applicable legal frameworks
- Lay-user friendly model description
- Detailed input data requirements

**Audit Configuration**:
- Audit type selection (opaque-box, translucent-box, or transparent-box)
- Model and/or training/test dataset access (as appropriate)
- Existing audit criteria (optional)

## Audit Criteria Framework

### Events
Events represent potential occurrences that could impact stakeholders, characterized by:
- **Name**: Descriptive identifier
- **Valence**: Positive or negative impact
- **Likelihood**: Probability of occurrence (1-10 scale)
- **Magnitude**: Severity of impact (1-10 scale)
- **Cause**: Root cause analysis (optional)
- **Categories**: Taxonomy classification
- **Entities Impacted**: Affected stakeholder groups

**Example**: "Low resource access might negatively affect risk score"
- Valence: Negative
- Likelihood: 5
- Magnitude: 7
- Cause: Visiting the doctor less creates a skew in the input data
- Entities Impacted: Patients

### Metrics
Metrics provide measurable ways to assess Events:
- Can be defined quantitatively or qualitatively
- Include threshold values for acceptability
- Created through structured metric creation process
- Track authorship and rationale

**Example**: "Parity of risk score between people with low income (<£15,000) versus people not on low income"

## Performance Analysis

### Assessment Options
- **Pass**: Criterion is met based on available evidence
- **Fail**: Criterion is not met based on available evidence
- **Inconclusive**: Insufficient evidence available to make a determination

### Audit Pathways

**Opaque-box ("Black-box") Auditing**:
- No access to AI model or training/test data
- Limited audit evidence available
- Relies primarily on external observation and documentation

**Translucent-box ("Grey-box") Auditing**:
- Partial access to model or data
- Some audit evidence available through API calls
- Balance between transparency and proprietary protection

**Transparent-box ("white-box") Auditing**:
- Full access to model and data
- Comprehensive audit evidence available
- Enables detailed technical analysis

### Outcome Evaluation
When model access is available, auditors can:
- Test data inputs through the model
- Assess criteria based on specific outcome instances
- Provide detailed instance-level feedback
- Document interpretation notes for each assessment

## Key Assumptions

- **Multiple Auditors**: Many auditors can audit a single AI application
- **Flexible Criteria**: Auditors can specify custom criteria or use pre-existing ones
- **Manual Assessment**: Auditing and evaluation require human judgment, not automation
- **Variable Evidence**: Audit evidence availability depends on chosen audit pathway
- **Lifecycle Coverage**: Audits can occur from conception through to deployment
- **Workflow Variation**: Different audit paths may require different processes

## Future Enhancements

**Planned Features**:
- Structured reports for audit instigators
- Enhanced feedback mechanisms (re-ranking, advanced markups)
- Training/test data feedback capabilities
- Model comparison functionality
- Risk taxonomy integration
- Audit loop closure mechanisms

**Advanced Analytics**:
- Automated fit assessment with risk taxonomies
- Pattern recognition across multiple audits
- Trend analysis and reporting
- Stakeholder impact visualization

## Getting Started

1. **For Audit Instigators**: Set up your AI application audit by providing comprehensive application information and selecting appropriate audit pathways
2. **For Auditors**: Accept audit invitations, review application overviews, define your audit criteria, and conduct systematic performance analysis
3. **For Organizations**: Integrate PHAWM into your AI governance framework to ensure responsible AI deployment and stakeholder engagement

---

*PHAWM represents a paradigm shift toward democratized AI auditing, enabling those most affected by AI systems to participate meaningfully in their evaluation and oversight.*