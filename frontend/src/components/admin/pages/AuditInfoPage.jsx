import React from 'react';
import { ChevronRight } from 'lucide-react';
import { PageShell, Field, TextInput, TextArea, PrimaryButton } from '../shared';

// Page 1 — name the audit. Presentational: state + submit handler come from props.
const AuditInfoPage = ({ auditForm, setAuditForm, submitAuditInfo, isSubmitting, isEdit = false }) => (
  <PageShell
    title={isEdit ? 'Audit Details' : 'Create Audit'}
    description={isEdit
      ? 'Edit the audit name and description. Use the left menu to jump to any page.'
      : "Start by naming your audit. You'll set up the application, model, and dataset in the following pages."}
    footer={
      <div className="ml-auto">
        <PrimaryButton onClick={submitAuditInfo} disabled={isSubmitting}>
          {isEdit ? 'Save & Continue' : 'Next: Create Application'}
          <ChevronRight className="w-4 h-4" />
        </PrimaryButton>
      </div>
    }
  >
    <Field label="Audit Name" required htmlFor="audit-name">
      <TextInput
        id="audit-name"
        value={auditForm.name}
        onChange={(e) => setAuditForm((p) => ({ ...p, name: e.target.value }))}
        placeholder="e.g. SAM Audit"
      />
    </Field>
    <Field label="Description" required htmlFor="audit-description">
      <TextArea
        id="audit-description"
        value={auditForm.description}
        onChange={(e) => setAuditForm((p) => ({ ...p, description: e.target.value }))}
        rows={3}
        placeholder="Describe the purpose of this audit..."
      />
    </Field>
  </PageShell>
);

export default AuditInfoPage;
