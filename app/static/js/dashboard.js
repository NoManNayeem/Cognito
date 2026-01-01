// Dashboard JavaScript

// Load statistics on page load
document.addEventListener('DOMContentLoaded', () => {
    loadStatistics();
    loadFiles();
    loadUrls();
    loadUsers();
});

async function loadStatistics() {
    try {
        const response = await fetch('/api/admin/stats');
        const data = await response.json();
        
        document.getElementById('totalUsers').textContent = data.total_users;
        document.getElementById('totalConversations').textContent = data.total_conversations;
        document.getElementById('totalFiles').textContent = data.total_files;
        document.getElementById('totalUrls').textContent = data.total_urls;
    } catch (error) {
        console.error('Failed to load statistics:', error);
    }
}

async function loadFiles() {
    try {
        const response = await fetch('/api/admin/files');
        const data = await response.json();
        
        const tbody = document.querySelector('#filesTable tbody');
        tbody.innerHTML = '';
        
        if (data.files && data.files.length > 0) {
            data.files.forEach(file => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${file.id}</td>
                    <td>${file.filename || 'N/A'}</td>
                    <td>
                        <button class="btn btn-sm btn-info" onclick="previewFile('${file.id}')">Preview</button>
                        <button class="btn btn-sm btn-warning" onclick="processFile('${file.id}')">Process</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteFile('${file.id}')">Delete</button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center">No files found</td></tr>';
        }
    } catch (error) {
        console.error('Failed to load files:', error);
        document.querySelector('#filesTable tbody').innerHTML = 
            '<tr><td colspan="3" class="text-center text-danger">Error loading files</td></tr>';
    }
}

async function loadUrls() {
    try {
        const response = await fetch('/api/admin/urls');
        const data = await response.json();
        
        const tbody = document.querySelector('#urlsTable tbody');
        tbody.innerHTML = '';
        
        if (data.urls && data.urls.length > 0) {
            data.urls.forEach(url => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${url.id}</td>
                    <td>${url.url || 'N/A'}</td>
                    <td>
                        <button class="btn btn-sm btn-info" onclick="previewUrl('${url.id}')">Preview</button>
                        <button class="btn btn-sm btn-warning" onclick="processUrl('${url.id}')">Process</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteUrl('${url.id}')">Delete</button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center">No URLs found</td></tr>';
        }
    } catch (error) {
        console.error('Failed to load URLs:', error);
        document.querySelector('#urlsTable tbody').innerHTML = 
            '<tr><td colspan="3" class="text-center text-danger">Error loading URLs</td></tr>';
    }
}

async function loadUsers() {
    try {
        const response = await fetch('/api/admin/users');
        const data = await response.json();
        
        const tbody = document.querySelector('#usersTable tbody');
        tbody.innerHTML = '';
        
        if (data.users && data.users.length > 0) {
            data.users.forEach(user => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${user.id}</td>
                    <td>${user.username}</td>
                    <td>
                        <span class="badge ${user.is_active ? 'bg-success' : 'bg-secondary'}">
                            ${user.is_active ? 'Active' : 'Inactive'}
                        </span>
                    </td>
                    <td>${user.scopes ? user.scopes.join(', ') : 'N/A'}</td>
                    <td>
                        <button class="btn btn-sm ${user.is_active ? 'btn-warning' : 'btn-success'}" 
                                onclick="toggleUserActivation(${user.id})">
                            ${user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">No users found</td></tr>';
        }
    } catch (error) {
        console.error('Failed to load users:', error);
        document.querySelector('#usersTable tbody').innerHTML = 
            '<tr><td colspan="5" class="text-center text-danger">Error loading users</td></tr>';
    }
}

async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a file');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/admin/files/upload?dataset_name=default', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('File uploaded successfully');
            bootstrap.Modal.getInstance(document.getElementById('uploadFileModal')).hide();
            fileInput.value = '';
            loadFiles();
            loadStatistics();
        } else {
            alert(`Error: ${data.detail || 'Failed to upload file'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function addUrl() {
    const urlInput = document.getElementById('urlInput');
    const url = urlInput.value.trim();
    
    if (!url) {
        alert('Please enter a URL');
        return;
    }
    
    try {
        const response = await fetch('/api/admin/urls', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                dataset_name: 'default'
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('URL added successfully');
            bootstrap.Modal.getInstance(document.getElementById('addUrlModal')).hide();
            urlInput.value = '';
            loadUrls();
            loadStatistics();
        } else {
            alert(`Error: ${data.detail || 'Failed to add URL'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function deleteFile(fileId) {
    if (!confirm('Are you sure you want to delete this file?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/files/${fileId}?dataset_name=default`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('File deleted successfully');
            loadFiles();
            loadStatistics();
        } else {
            alert(`Error: ${data.detail || 'Failed to delete file'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function deleteUrl(urlId) {
    if (!confirm('Are you sure you want to delete this URL?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/urls/${urlId}?dataset_name=default`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('URL deleted successfully');
            loadUrls();
            loadStatistics();
        } else {
            alert(`Error: ${data.detail || 'Failed to delete URL'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function previewFile(fileId) {
    try {
        const response = await fetch(`/api/admin/files/${fileId}/preview`);
        const data = await response.json();
        alert(`Preview:\n\n${data.preview}`);
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function previewUrl(urlId) {
    try {
        const response = await fetch(`/api/admin/urls/${urlId}/preview`);
        const data = await response.json();
        alert(`Preview:\n\n${data.preview}`);
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function processFile(fileId) {
    try {
        const response = await fetch(`/api/admin/files/${fileId}/process?dataset_name=default`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('File processing started');
        } else {
            alert(`Error: ${data.detail || 'Failed to process file'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function processUrl(urlId) {
    try {
        const response = await fetch(`/api/admin/urls/${urlId}/process?dataset_name=default`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('URL processing started');
        } else {
            alert(`Error: ${data.detail || 'Failed to process URL'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function toggleUserActivation(userId) {
    try {
        const response = await fetch(`/api/admin/users/${userId}/activate`, {
            method: 'PATCH'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert(data.message);
            loadUsers();
            loadStatistics();
        } else {
            alert(`Error: ${data.detail || 'Failed to toggle user activation'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}
