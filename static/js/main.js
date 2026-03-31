// static/js/main.js
// Form validation utilities
function validateForm(formId) {
    const form = document.getElementById(formId);
    const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.style.borderColor = '#e74c3c';
            isValid = false;
        } else {
            input.style.borderColor = '#ddd';
        }
    });
    
    return isValid;
}

// Auto-hide alerts after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// Book search with debounce
let searchTimeout;
function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        const searchInput = document.querySelector('input[name="search"]');
        if (searchInput) {
            const form = searchInput.closest('form');
            if (form) form.submit();
        }
    }, 500);
}

// Add to global scope for HTML onclick handlers
window.requestBook = function(bookId) {
    const modal = document.getElementById('requestModal');
    if (modal) {
        modal.style.display = 'flex';
        window.currentBookId = bookId;
    }
};

window.closeModal = function() {
    const modal = document.getElementById('requestModal');
    if (modal) {
        modal.style.display = 'none';
    }
};

// Message sending
async function sendMessage(receiverId, requestId) {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    
    if (!message) {
        alert('Please enter a message');
        return;
    }
    
    const formData = new FormData();
    formData.append('receiver_id', receiverId);
    formData.append('message', message);
    if (requestId) formData.append('request_id', requestId);
    
    try {
        const response = await fetch('/send_message', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        if (response.ok) {
            messageInput.value = '';
            loadMessages(receiverId);
        } else {
            alert(result.error);
        }
    } catch (error) {
        console.error('Error sending message:', error);
        alert('Failed to send message');
    }
}

// Load messages
async function loadMessages(userId) {
    try {
        const response = await fetch(`/get_messages/${userId}`);
        const messages = await response.json();
        
        const messagesContainer = document.getElementById('messagesContainer');
        if (messagesContainer) {
            messagesContainer.innerHTML = messages.map(msg => `
                <div class="message ${msg.is_owner ? 'message-owner' : 'message-other'}">
                    <strong>${msg.username}</strong>
                    <p>${msg.message}</p>
                    <small>${msg.sent_date}</small>
                </div>
            `).join('');
            
            // Scroll to bottom
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    } catch (error) {
        console.error('Error loading messages:', error);
    }
}

// Request response
async function respondRequest(requestId, action) {
    const formData = new FormData();
    formData.append('action', action);
    
    try {
        const response = await fetch(`/respond_request/${requestId}`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        if (response.ok) {
            location.reload();
        } else {
            alert(result.error);
        }
    } catch (error) {
        console.error('Error responding to request:', error);
        alert('Failed to process request');
    }
}

// Add to global scope
window.respondRequest = respondRequest;
window.sendMessage = sendMessage;

// Image preview
function previewImage(input) {
    const preview = document.getElementById('imagePreview');
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            if (preview) {
                preview.src = e.target.result;
                preview.style.display = 'block';
            }
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// Initialize socket connection for real-time messages (optional)
if (typeof io !== 'undefined') {
    const socket = io();
    
    socket.on('new_message', (data) => {
        const currentUserId = window.currentUserId;
        if (data.sender_id !== currentUserId && 
            (data.receiver_id === currentUserId || data.sender_id === currentUserId)) {
            loadMessages(data.sender_id);
        }
    });
}
