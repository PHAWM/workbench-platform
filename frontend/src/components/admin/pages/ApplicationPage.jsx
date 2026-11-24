import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { PageShell, Field, TextInput, TextArea, Select, PrimaryButton, SecondaryButton } from '../shared';

// Page 2 — create the AI application. Presentational; state + handlers via props.
const ApplicationPage = ({ applicationForm, setApplicationForm, submitApplication, isSubmitting, onBack, isEdit = false }) => {
  const set = (key) => (e) => setApplicationForm((p) => ({ ...p, [key]: e.target.value }));

  return (
    <PageShell
      title="Create Application"
      description="Define the AI application to be audited."
      footer={
        <>
          <SecondaryButton onClick={onBack}>
            <ChevronLeft className="w-4 h-4" /> Back
          </SecondaryButton>
          <PrimaryButton onClick={submitApplication} disabled={isSubmitting}>
            {isSubmitting ? 'Saving...' : isEdit ? 'Save Application' : 'Create Application'}
            <ChevronRight className="w-4 h-4" />
          </PrimaryButton>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-4">
        <Field label="Application Name" required>
          <TextInput value={applicationForm.name} onChange={set('name')} placeholder="e.g. SAM" />
        </Field>
        <Field label="Organisation" required>
          <TextInput value={applicationForm.organisation} onChange={set('organisation')} placeholder="e.g. NHS Trust" />
        </Field>
        <Field label="Description" required className="col-span-2">
          <TextArea value={applicationForm.description} onChange={set('description')} rows={2} placeholder="Describe the application..." />
        </Field>
        <Field label="URL" required>
          <TextInput type="url" value={applicationForm.url} onChange={set('url')} placeholder="https://example.com/app" />
        </Field>
        <Field label="Access Type">
          <Select value={applicationForm.access_type} onChange={set('access_type')}>
            <option value="0">Opaque</option>
            <option value="1">Translucent</option>
            <option value="2">Transparent</option>
          </Select>
        </Field>
        <Field label="Business Case" className="col-span-2">
          <TextArea value={applicationForm.business_case} onChange={set('business_case')} rows={2} placeholder="Describe the Business Case of your Application..." />
        </Field>
        <Field label="Legal Framework" className="col-span-2">
          <TextArea value={applicationForm.legal_framework} onChange={set('legal_framework')} rows={2} placeholder="Describe the Legal Framework that has been applied for your Application..." />
        </Field>
      </div>

      <div>
        <h4 className="text-md font-semibold text-gray-700 mb-3">Testing &amp; Evaluation</h4>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Model Details" className="col-span-2">
            <TextArea value={applicationForm.te_model_details} onChange={set('te_model_details')} rows={2} placeholder="Describe the model used..." />
          </Field>
          <Field label="Dataset Details" className="col-span-2">
            <TextArea value={applicationForm.te_dataset_details} onChange={set('te_dataset_details')} rows={2} placeholder="Describe the dataset and how outputs are generated..." />
          </Field>
          <Field label="Testing Details">
            <TextInput value={applicationForm.te_testing_details} onChange={set('te_testing_details')} placeholder="e.g. It has been tested before, internally." />
          </Field>
          <Field label="Audit Instigator Details">
            <TextInput value={applicationForm.te_audit_instigator_details} onChange={set('te_audit_instigator_details')} placeholder="Name, role, contact email" />
          </Field>
        </div>
      </div>

      <div>
        <h4 className="text-md font-semibold text-gray-700 mb-3">Deployment</h4>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Version / Status" className="col-span-2">
            <TextArea value={applicationForm.deploy_version} onChange={set('deploy_version')} rows={2} placeholder="e.g. Deployed. Used by..." />
          </Field>
          <Field label="Environment" className="col-span-2">
            <TextArea value={applicationForm.deploy_environment} onChange={set('deploy_environment')} rows={2} placeholder="Describe the deployment environment..." />
          </Field>
        </div>
      </div>
    </PageShell>
  );
};

export default ApplicationPage;
