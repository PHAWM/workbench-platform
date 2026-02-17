import React, { useState, useEffect, useRef } from 'react'; // Added useRef
import { ChevronDown, ChevronUp, ArrowLeft, ArrowRight } from 'lucide-react';
import { Navigation } from '../components/navigation/Navigation';
import { useParams, useNavigate } from 'react-router-dom';
import { aiApplicationAPI } from '../api/apiService';
import { isAuditReadOnly } from '../utils/auditUtils';
import { useApi } from '../context/apiContext';
import { useOnboarding } from '../context/onboardingContext';

/* Collapsible Section */
const CollapsibleSection = ({ title, children, isOpen, onToggle, sectionRef }) => (
  <div className="mb-4" ref={sectionRef}>
    <div
      className="bg-gradient-to-r from-purple-50 to-blue-50 border-2 border-purple-200 rounded-lg p-4 cursor-pointer hover:shadow-md transition-shadow"
      onClick={(e) => onToggle(e)}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
        {isOpen ? (
          <ChevronUp className="w-5 h-5 text-gray-600" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-600" />
        )}
      </div>
      {isOpen && <div className="mt-4 space-y-3">{children}</div>}
    </div>
  </div>
);

/* Reusable Form Field */
const FormField = ({
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
  options = [],
  disabled = false,
  rows,
}) => (
  <div className="space-y-2">
    {label && <label className="block text-sm font-medium text-gray-700">{label}</label>}
    {type === 'select' ? (
      <select
        value={value}
        onChange={onChange}
        disabled={disabled}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
      >
        <option value="">Select {label}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    ) : type === 'textarea' ? (
        <textarea
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
          rows={rows || 5}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
        />
      ) : (
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
      />
    )}
  </div>
);

const AIApplicationOverview = () => {
  const { auditStatus, accessType, setAuditStatus, setAccessType } = useApi();
  const { checkAndStartOnboarding } = useOnboarding();
  const isReadOnly = isAuditReadOnly(auditStatus);
  const { auditId } = useParams();
  const navigate = useNavigate();

  // Trigger onboarding when entering this page from dashboard
  useEffect(() => {
    checkAndStartOnboarding('ai-application');
  }, [checkAndStartOnboarding]);

  const [currentPage, setCurrentPage] = useState('ai-application');
  const [auditState, setAuditState] = useState({
    hasSelectedMetrics: false,
    hasEvaluated: false,
  });

  const [openSections, setOpenSections] = useState({
    'ai-summary': true,
    'audit-details': false,
    'application-environment': false,
    'development-pipeline': false,
    'model': false,
    'dataset': false,
    'testing-evaluation': false,
    'deployment': false,
    'business-case': false,
    'legal-framework': false,
  });

  const [formData, setFormData] = useState({
    id: '',
    name: '',
    application_name: '',
    application_description: '',
    application_organisation: '',
    application_url: '',
    access_type: '',
    application_models: [],
    application_datasets: [],
    testing_evaluation: {
      testing_details: '',
      model_details: '',
      dataset_details: '',
      audit_instigator_details: '',
    },
    deployment: {
      environment: '',
      version: '',
      audit_instigator_details: '',
    },
    business_case: '',
    legal_framework: '',
  });

  // Create refs for each section
  const sectionRefs = useRef({
    'ai-summary': null,
    'audit-details': null,
    'application-environment': null,
    'development-pipeline': null,
    'model': null,
    'dataset': null,
    'testing-evaluation': null,
    'deployment': null,
    'business-case': null,
    'legal-framework': null,
  });

  /* Load persisted state */
  useEffect(() => {
    if (auditId) {
      try {
        const stored = localStorage.getItem(`audit_state_${auditId}`);
        if (stored) setAuditState(JSON.parse(stored));
      } catch (err) {
        console.error('Failed to load persisted audit state:', err);
      }
    }
  }, [auditId]);

  /* Load data from API */
  useEffect(() => {
    const loadData = async () => {
      try {
        const response = await aiApplicationAPI.getApplicationOverview(auditId);
        if (!response) return;

        // Update global context
        setAuditStatus(response.status_text || '');
        setAccessType(response.access_type || '');

        setFormData({
          id: response.id,
          name: response.name,
          application_name: response.application_name || '',
          application_description: response.application_description || '',
          application_organisation: response.application_organisation || '',
          application_url: response.application_url || '',
          access_type: response.access_type || '',
          application_models: response.application_models || [],
          application_datasets: response.application_datasets || [],
          testing_evaluation: {
            testing_details: response.testing_evaluation?.testing_details || '',
            model_details: response.testing_evaluation?.model_details || '',
            dataset_details: response.testing_evaluation?.dataset_details || '',
            audit_instigator_details:
              response.testing_evaluation?.audit_instigator_details || '',
          },
          deployment: {
            environment: response.deployment?.environment || '',
            version: response.deployment?.version || '',
          },
          audit_instigator: response.testing_evaluation?.audit_instigator_details || "",
          business_case: response.business_case || "",
          legal_framework: response.legal_framework || "",
        });
      } catch (err) {
        console.error('Error loading application data:', err);
      }
    };

    loadData();
  }, [auditId, setAccessType, setAuditStatus]);

  // Scroll to section when it's opened
  const toggleSection = (section, event) => {
    if (event) {
      event.stopPropagation();
    }
    
    const willOpen = !openSections[section];
    
    // Toggle the section
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
    
    // Scroll to section if it's being opened
    if (willOpen) {
      setTimeout(() => {
        const sectionElement = sectionRefs.current[section];
        if (sectionElement) {
          sectionElement.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'nearest' 
          });
        }
      }, 100);
    }
  };

  // Special handler for nested sections to also open parent
  const toggleNestedSection = (section, parentSection, event) => {
    if (event) {
      event.stopPropagation();
    }
    
    const willOpen = !openSections[section];
    
    // Open parent section if it's closed
    if (!openSections[parentSection]) {
      setOpenSections((prev) => ({ ...prev, [parentSection]: true }));
    }
    
    // Toggle the nested section
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
    
    // Scroll to section if it's being opened
    if (willOpen) {
      setTimeout(() => {
        // Try to scroll to the nested section
        const sectionElement = sectionRefs.current[section];
        if (sectionElement) {
          sectionElement.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'nearest' 
          });
        } 
        // If nested section ref not available, scroll to parent
        else {
          const parentElement = sectionRefs.current[parentSection];
          if (parentElement) {
            parentElement.scrollIntoView({ 
              behavior: 'smooth', 
              block: 'start' 
            });
          }
        }
      }, 150); // Slightly longer delay to ensure parent is opened
    }
  };

  const handleNavigation = (pageId) => {
    setCurrentPage(pageId);
    if (pageId === 'dashboard') navigate('/dashboard');
    else if (pageId === 'profile') navigate('/profile');
    else if (auditId) navigate(`/${pageId}/${auditId}`);
    else navigate('/dashboard');
  };

  return (
    <div className="min-h-screen bg-purple-to-br from-purple-50 to-pink-50 p-4">
      <Navigation
        currentPage={currentPage}
        hasSelectedMetrics={auditState.hasSelectedMetrics}
        hasEvaluated={auditState.hasEvaluated}
        hasEnteredAudit={true}
        isReadOnly={isReadOnly}
        onNavigate={handleNavigation}
      />
      
      {/* Purpose Box - Added as per wireframe */}
      <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md" data-onboarding="purpose-box">
        <div className="flex items-start">
          <div>
            <p className="text-gray-700">
              This is the AI Application Overview page. The purpose of this page is to provide information on the AI Application you are asked to audit and the auditing context. Once you have read through the information, you can move forward to the Audit Criteria page.
            </p>
          </div>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-1/4" data-onboarding="sidebar">
          <div className="bg-gradient-to-b from-purple-100 to-pink-100 rounded-2xl p-4 border-2 border-purple-200">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">
              {formData.name}
            </h2>
            <div className="space-y-2">
              {/* Level 1: Main sections */}
              <button
                onClick={() => toggleSection('ai-summary')}
                className={`w-full text-left px-3 py-2 rounded-md transition-colors ${
                  openSections['ai-summary']
                    ? 'bg-purple-200 text-purple-900 border border-purple-300'
                    : 'bg-gradient-to-b from-purple-100 to-pink-100 text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
              >
                AI Application Summary
              </button>
              
              <button
                onClick={() => toggleSection('audit-details')}
                className={`w-full text-left px-3 py-2 rounded-md transition-colors ${
                  openSections['audit-details']
                    ? 'bg-purple-200 text-purple-900 border border-purple-300'
                    : 'bg-gradient-to-b from-purple-100 to-pink-100 text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
              >
                Audit Details
              </button>
              
              <button
                onClick={() => toggleSection('application-environment')}
                className={`w-full text-left px-3 py-2 rounded-md transition-colors ${
                  openSections['application-environment']
                    ? 'bg-purple-200 text-purple-900 border border-purple-300'
                    : 'bg-gradient-to-b from-purple-100 to-pink-100 text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
              >
                AI Application Environment
              </button>
              
              {/* AI Application Development Pipeline as a main section */}
              <button
                onClick={() => toggleSection('development-pipeline')}
                className={`w-full text-left px-3 py-2 rounded-md transition-colors ${
                  openSections['development-pipeline']
                    ? 'bg-purple-200 text-purple-900 border border-purple-300'
                    : 'bg-gradient-to-b from-purple-100 to-pink-100 text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
              >
                AI Application Development Pipeline
              </button>
              
              {/* Nested items under Development Pipeline */}
              {openSections['development-pipeline'] && (
                <div className="ml-6 space-y-2 border-l-2 border-purple-300 pl-3">
                  <button
                    onClick={(e) => toggleNestedSection('business-case', 'development-pipeline', e)}
                    className={`w-full text-left px-3 py-2 rounded-md transition-colors text-sm ${
                      openSections['business-case']
                        ? 'bg-purple-100 text-purple-800 border border-purple-200'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    Business Case
                  </button>
                  <button
                    onClick={(e) => toggleNestedSection('dataset', 'development-pipeline', e)}
                    className={`w-full text-left px-3 py-2 rounded-md transition-colors text-sm ${
                      openSections['dataset']
                        ? 'bg-purple-100 text-purple-800 border border-purple-200'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    Dataset
                  </button>
                  <button
                    onClick={(e) => toggleNestedSection('model', 'development-pipeline', e)}
                    className={`w-full text-left px-3 py-2 rounded-md transition-colors text-sm ${
                      openSections['model']
                        ? 'bg-purple-100 text-purple-800 border border-purple-200'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    AI Model Architecture
                  </button>
                  <button
                    onClick={(e) => toggleNestedSection('testing-evaluation', 'development-pipeline', e)}
                    className={`w-full text-left px-3 py-2 rounded-md transition-colors text-sm ${
                      openSections['testing-evaluation']
                        ? 'bg-purple-100 text-purple-800 border border-purple-200'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    Testing and Evaluation
                  </button>
                  <button
                    onClick={(e) => toggleNestedSection('deployment', 'development-pipeline', e)}
                    className={`w-full text-left px-3 py-2 rounded-md transition-colors text-sm ${
                      openSections['deployment']
                        ? 'bg-purple-100 text-purple-800 border border-purple-200'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    Deployment
                  </button>
                </div>
              )}
              
              <button
                onClick={() => toggleSection('legal-framework')}
                className={`w-full text-left px-3 py-2 rounded-md transition-colors ${
                  openSections['legal-framework']
                    ? 'bg-purple-200 text-purple-900 border border-purple-300'
                    : 'bg-gradient-to-b from-purple-100 to-pink-100 text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
              >
                Legal Framework
              </button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1" data-onboarding="content">
          <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
            {/* AI Application Summary */}
            <CollapsibleSection
              title="AI Application Summary"
              isOpen={openSections['ai-summary']}
              onToggle={() => toggleSection('ai-summary')}
              sectionRef={(el) => (sectionRefs.current['ai-summary'] = el)}
            >
              <FormField
                type="textarea"
                value={formData.application_description}
                disabled
                rows={8}
              />
            </CollapsibleSection>

            {/* Audit Details */}
            <CollapsibleSection
              title={
                      <span>
                        Audit Details:{" "}
                        <span className="text-base font-semibold text-gray-700">
                          Who has initiated and set up this audit and for which purpose.
                        </span>
                      </span>
                    }
              isOpen={openSections['audit-details']}
              onToggle={() => toggleSection('audit-details')}
              sectionRef={(el) => (sectionRefs.current['audit-details'] = el)}
            >
              <FormField
                type="textarea"
                value={formData.testing_evaluation.audit_instigator_details}
                disabled
              />
            </CollapsibleSection>

            {/* AI Application Environment */}
            <CollapsibleSection
              title={
                    <span>
                      AI Application Environment:{" "}
                      <span className="text-base font-semibold text-gray-700">
                        Where and how the AI application is used.
                      </span>
                    </span>
                  }
              isOpen={openSections['application-environment']}
              onToggle={() => toggleSection('application-environment')}
              sectionRef={(el) => (sectionRefs.current['application-environment'] = el)}
            >
              <FormField
                type="textarea"
                value={formData.deployment.environment}
                disabled
              />
            </CollapsibleSection>

            {/* AI Application Development Pipeline - Parent Section */}
            <CollapsibleSection
              title={
                    <span>
                      AI Application Development Pipeline:{" "}
                      <span className="text-base font-semibold text-gray-700">
                        Why and how the AI Application is built and run.
                      </span>
                    </span>
                  }
              isOpen={openSections['development-pipeline']}
              onToggle={() => toggleSection('development-pipeline')}
              sectionRef={(el) => (sectionRefs.current['development-pipeline'] = el)}
            >
              <div onClick={(e) => e.stopPropagation()}>
                <p className="text-gray-600 mb-4">
                  The AI Application Development Pipeline includes the following components:
                </p>

                {/* Business Case - Nested under Development Pipeline */}
                <div className="ml-4 mb-4">
                  <CollapsibleSection
                    title={
                    <span>
                      Business Case:{" "}
                      <span className="text-base font-semibold text-gray-700">
                        What the motivation for and goal of the AI Application is.
                      </span>
                    </span>
                  }
                    isOpen={openSections['business-case']}
                    onToggle={() => toggleNestedSection('business-case', 'development-pipeline')}
                    sectionRef={(el) => (sectionRefs.current['business-case'] = el)}
                  >
                    <FormField 
                      type="textarea" 
                      value={formData.business_case}
                      disabled
                      rows={10} 
                    />
                  </CollapsibleSection>
                </div>
                
                {/* Dataset - Nested under Development Pipeline */}
                <div className="ml-4 mb-4">
                  <CollapsibleSection
                    title={
                    <span>
                      Dataset:{" "}
                      <span className="text-base font-semibold text-gray-700">
                        Characteristics of the data used to create/train and then test the AI Application.
                      </span>
                    </span>
                    }
                    isOpen={openSections['dataset']}
                    onToggle={() => toggleNestedSection('dataset', 'development-pipeline')}
                    sectionRef={(el) => (sectionRefs.current['dataset'] = el)}
                  >
                    <FormField
                      type="textarea"
                      value={formData.testing_evaluation.dataset_details}
                      disabled
                      rows={8}
                    />
                  </CollapsibleSection>
                </div>
                
                {/* AI Model Architecture - Nested under Development Pipeline */}
                <div className="ml-4 mb-4">
                  <CollapsibleSection
                    title={
                    <span>
                      AI Model Architecture:{" "}
                      <span className="text-base font-semibold text-gray-700">
                        How the AI Applications makes decisions.
                      </span>
                    </span>
                    }
                    isOpen={openSections['model']}
                    onToggle={() => toggleNestedSection('model', 'development-pipeline')}
                    sectionRef={(el) => (sectionRefs.current['model'] = el)}
                  >
                    {formData.testing_evaluation?.model_details ? (
                      <FormField
                        type="textarea"
                        value={formData.testing_evaluation.model_details}
                        disabled
                        rows={8}
                      />
                    ) : (
                      <p className="text-gray-500 italic">No model information available</p>
                    )}
                  </CollapsibleSection>
                </div>
                
                {/* Testing and Evaluation - Nested under Development Pipeline */}
                <div className="ml-4 mb-4">
                  <CollapsibleSection
                    title={
                    <span>
                      Testing and Evaluation:{" "}
                      <span className="text-base font-semibold text-gray-700">
                        How the Application has been previously assessed.
                      </span>
                    </span>
                    }
                    isOpen={openSections['testing-evaluation']}
                    onToggle={() => toggleNestedSection('testing-evaluation', 'development-pipeline')}
                    sectionRef={(el) => (sectionRefs.current['testing-evaluation'] = el)}
                  >
                    <FormField 
                      label="Last Tested"
                      value={formData.testing_evaluation.testing_details} 
                      disabled 
                    />
                  </CollapsibleSection>
                </div>
                
                {/* Deployment - Nested under Development Pipeline */}
                <div className="ml-4 mb-4">
                  <CollapsibleSection
                    title={
                    <span>
                      Deployment:{" "}
                      <span className="text-base font-semibold text-gray-700">
                        How and where is the AI Application being released.
                      </span>
                    </span>
                    }
                    isOpen={openSections['deployment']}
                    onToggle={() => toggleNestedSection('deployment', 'development-pipeline')}
                    sectionRef={(el) => (sectionRefs.current['deployment'] = el)}
                  >
                    <FormField 
                      label="Version"
                      value={formData.deployment.version} 
                      disabled 
                    />
                  </CollapsibleSection>
                </div>
              </div>
            </CollapsibleSection>

            {/* Legal Framework */}
            <CollapsibleSection
              title={
                    <span>
                      Legal Framework:{" "}
                      <span className="text-base font-semibold text-gray-700">
                        Which legal obligations does the AI Application have to fulfil.
                      </span>
                    </span>
              }
              isOpen={openSections['legal-framework']}
              onToggle={() => toggleSection('legal-framework')}
              sectionRef={(el) => (sectionRefs.current['legal-framework'] = el)}
            >
              <FormField 
                type="textarea" 
                value={formData.legal_framework} 
                disabled 
              />
            </CollapsibleSection>
          </div>
        </div>
      </div>
      
      <div className="flex gap-4 justify-between pt-6" data-onboarding="navigation-buttons">
        <button
          onClick={() => navigate("/dashboard")}
          className="flex items-center gap-2 hover:bg-purple-200 px-4 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100"
        >
          <ArrowLeft /> Back to Dashboard
        </button>
        <button
          onClick={() => navigate(`/audit-criteria/${auditId}`)}
          className="flex items-center gap-2 hover:bg-purple-200 px-4 py-3 rounded-full text-base font-semibold transition-colors border-2 border-purple-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-purple-100"
        >
          Next to Audit Criteria <ArrowRight />
        </button>
      </div>
    </div>
  );
};

export default AIApplicationOverview;