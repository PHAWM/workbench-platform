import React, { useState, useEffect } from 'react';
import { Navigation } from '../components/navigation/Navigation';
import { useParams, useNavigate } from 'react-router-dom';
import {
    dashboardAPI,
    getAccessTypeLabel
} from '../api/apiService';
import { useOnboarding } from '../context/onboardingContext';
import { createDashboardHandlers } from '../handlers/dashboardHandlers';
import { InfoTooltip } from '../components/ui/toolTip';

const Dashboard = () => {
  let { auditId } = useParams();
  const navigate = useNavigate();
  const { startOnboardingFromDashboard, endAuditSession } = useOnboarding();

  const [selectedAuditId, setSelectedAuditId] = useState(null);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [availableAudits, setAvailableAudits] = useState([]);
  const [availableAuditsList, setAvailableAuditsList] = useState([]);

  // End onboarding session when returning to dashboard
  useEffect(() => {
    endAuditSession();
  }, [endAuditSession]);

  useEffect(() => {
    loadAuditData();
  }, []);
  const loadAuditData = async () => {
    // Read the data from the api
    const [auditResponse] = await Promise.all([dashboardAPI.getApplications()])
    // Transform the data into what the componet requires
    const transformedAudits = transformApiDashboardToComponentFormat(auditResponse);
    // Set the state
    setAvailableAudits(transformedAudits);
    const list = transformedAudits.map(audit => {
      return {
        name: audit.auditName,
        id: audit.auditId,
      }
    })
    setAvailableAuditsList(list);
  }
  const transformApiDashboardToComponentFormat = (apiResponse) => {
    const auditsArray = apiResponse.audits || apiResponse;

    // console.log(auditsArray);

    // We need iterate through the array and map all the information from the with the what we need in the components

    return auditsArray.map(audit => {
      return {
        auditId: audit.id,
        auditName: audit.name,
        aiApplication: audit.application_name,
        instigatorName: audit.audit_instigator,
        organizationName: audit.application_organisation,
        // show this to the dashboard. show label called status: value of the status text.
        status: audit.status_text, 
        accessType: getAccessTypeLabel(audit.access_type),
        auditStatus: parseInt(audit.completion_percentage),
        auditRecomendationText: audit.recommendation,
        action: "Enter Audit",
      };

    });
  };

  // Create dashboard handlers using the handler factory
  const { handleNavigation, handleAuditClick } = createDashboardHandlers({
    setCurrentPage,
    setSelectedAuditId,
    navigate,
    auditId,
    startOnboardingFromDashboard
  });
  return (
    <div className="min-h-screen bg-purple-to-br from-purple-50 to-pink-50 p-4">
         <Navigation  
          currentPage={currentPage}
          onNavigate={handleNavigation} 
        />

        {/* Purpose Box - Added as per wireframe */}
         <div className="mb-6 bg-b7efff rounded-2xl border-2 border-purple-300 p-6 shadow-md">
           <div className="flex items-start">
              <div>
                 <p className="text-gray-700">
                  This is the Dashboard page. This is where you can enter and/or view (if completed) the audits you have been invited to participate in. Select an audit you wish to enter or view to proceed to the AI Application Overview page, by clicking the Enter Audit or View Audit button.
                  </p>
              </div>
            </div>
          </div>

        <div className="flex gap-6">
          {/* Sidebar Audit List */}
          <div className="w-1/4">
            <div className="bg-gradient-to-b from-purple-100 to-pink-100 rounded-2xl p-4 border-2 border-purple-200">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Audit List</h3>
              <div className="space-y-2">
                {availableAuditsList.map((audit) => {
                  const auditData = availableAudits.find(a => a.auditId === audit.id);
                  return (
                    <div
                      key={audit.id}
                      onClick={() => handleAuditClick(audit.id, auditData?.status)}
                      className={`w-full text-left px-3 py-2 rounded-md transition-colors cursor-pointer ${
                        selectedAuditId === audit.id
                          ? "bg-purple-200 text-purple-900 border border-purple-300"
                          : "bg-gradient-to-b from-purple-100 to-pink-100 text-gray-700 border border-gray-300 hover:bg-gray-50"
                      }`}
                    >
                    {audit.name}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Main Content */}     
          <div className="flex-1 h-full"> 
            <div className="bg-purple rounded-3xl border-2 border-purple-200 p-6 shadow-lg w-full">
            <h3 className="text-lg font-semibold text-gray-800 text-left mb-4">Audit Details</h3>
            <div className="space-y-4">
              {availableAudits.map((audit, index) => (
                <div
                  key={index}
                  // Styling for each audit item
                  className="flex items-center justify-between p-6 rounded-2xl  border-2 border-purple-200 bg-gradient-to-r from-purple-50 to-pink-50 shadow-lg w-full flex gap-4"       
                >
                  {/* Left side: audit info */}
                  <div className="flex-1">
                    <div className="font-medium text-gray-800 mb-1 flex items-center gap-1.5">
                      {audit.auditName}
                      
                    </div>
                    <div className="text-sm text-gray-500">
                      {audit.organizationName}
                      <InfoTooltip content="Check the Audit Details in the AI Application Overview." side="bottom" />
                    </div>
                  </div>

                  <div className="flex-1 gap-2">
                    <div className="font-medium text-gray-800 mb-1">AI Application</div>
                    <div className="text-sm text-gray-500">
                      {audit.aiApplication}
                    </div>
                  </div>

                  <div className="flex-1 items-center gap-2">
                    <div className="font-medium text-gray-800 mb-1">Status</div>
                    <div className="text-sm text-gray-500">
                      {audit.status}
                    </div>

                  </div>
                  {/* Right side: progress and button */}
                  <div className="flex-1 items-center gap-2 align-">
                    {/* Progress Bar */}
                    <div className="font-medium text-gray-800 mb-1">Audit Status</div>
                    <div className="w-32">
                      <div className="w-full bg-gray-200 rounded-full h-3 mt-1 mb-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${audit.auditStatus}%` }}
                        ></div>
                      </div>
                      {/* <div className="text-xs text-gray-500 mt-1">{audit.auditStatus}%</div> */}
                    </div>
                  </div>
                    
                  <div className="flex gap-2">
                    {/* Whether Enter Audit button displayed or not */}
                    {(audit.status !== "Submitted") ? (
                      <button
                        className="bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-sm font-semibold  border-2 border-purple-200"
                        onClick={() => handleAuditClick(audit.auditId, audit.status)}
                      >
                      {audit.action}
                      </button>
                    ) : (
                      <button
                        className="bg-purple-100 hover:bg-purple-200 px-4 py-2 rounded-full text-sm font-semibold  border-2 border-purple-200"
                        onClick={() => handleAuditClick(audit.auditId, audit.status)}
                      >
                      View Audit
                      </button>
                    )}

                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
     </div>
    </div>
  );
};

export default Dashboard;