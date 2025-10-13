// Main JavaScript for SalesBreachPro

// Global application object
window.SalesBreachPro = {
    init: function() {
        console.log('SalesBreachPro initialized');
        this.setupEventListeners();
        this.initTooltips();
    },
    
    setupEventListeners: function() {
        // Auto-hide alerts after 5 seconds
        setTimeout(function() {
            $('.alert').fadeOut();
        }, 5000);
        
        // Confirm delete actions
        $(document).on('click', '.delete-confirm', function(e) {
            if (!confirm('Are you sure you want to delete this item?')) {
                e.preventDefault();
            }
        });
        
        // Loading state for buttons
        $(document).on('click', '.btn-loading', function() {
            const $btn = $(this);
            const originalText = $btn.html();
            $btn.data('original-text', originalText);
            $btn.html('<i class="fas fa-spinner fa-spin me-1"></i>Processing...');
            $btn.prop('disabled', true);
        });
    },
    
    initTooltips: function() {
        // Initialize Bootstrap tooltips
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    },
    
    // API helper functions
    api: {
        get: function(url, callback) {
            fetch(url)
                .then(response => response.json())
                .then(data => callback(null, data))
                .catch(error => callback(error, null));
        },
        
        post: function(url, data, callback) {
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => callback(null, data))
            .catch(error => callback(error, null));
        }
    },
    
    // Utility functions
    utils: {
        formatNumber: function(num) {
            return new Intl.NumberFormat().format(num);
        },
        
        formatDate: function(dateString) {
            return new Date(dateString).toLocaleDateString();
        },
        
        showAlert: function(message, type = 'info') {
            const alertHtml = `
                <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
            $('.container').first().prepend(alertHtml);
        },
        
        copyToClipboard: function(text) {
            navigator.clipboard.writeText(text).then(function() {
                SalesBreachPro.utils.showAlert('Copied to clipboard!', 'success');
            });
        }
    },
    
    // Dashboard specific functions
    dashboard: {
        refreshStats: function() {
            SalesBreachPro.api.get('/api/stats', function(error, data) {
                if (error) {
                    console.error('Error refreshing stats:', error);
                    SalesBreachPro.utils.showAlert('Failed to refresh stats', 'danger');
                } else {
                    // Update stats on page
                    SalesBreachPro.dashboard.updateStatsDisplay(data);
                }
            });
        },
        
        updateStatsDisplay: function(stats) {
            // Update stat cards with new data
            // This would be implemented based on the specific HTML structure
            console.log('Updating stats:', stats);
        }
    },
    
    // CSV Upload functions - DISABLED to prevent conflicts with enhanced upload system
    upload: {
        init: function() {
            // Disabled - upload functionality is handled by ContactUploader in upload.html template
            console.log('Upload functionality handled by template-specific ContactUploader');
        }
    },
    
    // Campaign management functions
    campaigns: {
        createCampaign: function(formData) {
            // Implementation for campaign creation
            console.log('Creating campaign:', formData);
        },
        
        pauseCampaign: function(campaignId) {
            if (confirm('Are you sure you want to pause this campaign?')) {
                // API call to pause campaign
                console.log('Pausing campaign:', campaignId);
            }
        },
        
        deleteCampaign: function(campaignId) {
            if (confirm('Are you sure you want to delete this campaign? This action cannot be undone.')) {
                // API call to delete campaign
                console.log('Deleting campaign:', campaignId);
            }
        }
    },
    
    // Breach lookup functions
    breach: {
        lookupDomain: function(domain, callback) {
            SalesBreachPro.api.get(`/api/breach-lookup/${domain}`, function(error, data) {
                if (callback) callback(error, data);
            });
        },
        
        displayBreachInfo: function(breachData) {
            // Display breach information in UI
            console.log('Displaying breach info:', breachData);
        }
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    SalesBreachPro.init();
    
    // Page-specific initialization  
    // Upload functionality is handled by ContactUploader in upload.html template
});

// jQuery document ready (for compatibility)
$(document).ready(function() {
    // Additional jQuery-based initialization can go here
});

// Export for global access
window.App = SalesBreachPro;