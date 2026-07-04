// API配置
const API_BASE_URL = 'http://localhost:3002';
const SUMMARY_API_URL = 'http://localhost:5001';
const RETRIEVE_API_URL = 'http://localhost:5002';
const TRANSLATE_API_URL = 'http://localhost:5003'; // 暂时空着
const REVIEW_API_URL = 'http://localhost:5004'; // 暂时空着

// 页面切换函数
function showPage(pageName) {
    // 隐藏所有页面
    const pages = document.querySelectorAll('.page');
    pages.forEach(page => page.style.display = 'none');
    
    // 显示目标页面
    const targetPage = document.getElementById(`${pageName}-page`);
    if (targetPage) {
        targetPage.style.display = 'block';
    }
    
    // 更新导航链接状态
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => link.classList.remove('active'));
    const activeLink = document.querySelector(`[onclick="showPage('${pageName}')"]`);
    if (activeLink) {
        activeLink.classList.add('active');
    }
    
    // 如果是个人主页，加载用户信息
    if (pageName === 'profile') {
        loadProfileInfo();
    }
}

// 登录注册功能

// 切换到注册页面
function switchToRegister() {
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('register-form').style.display = 'flex';
    document.getElementById('auth-title').textContent = '注册';
    clearAuthMessage();
}

// 切换到登录页面
function switchToLogin() {
    document.getElementById('register-form').style.display = 'none';
    document.getElementById('login-form').style.display = 'flex';
    document.getElementById('auth-title').textContent = '登录';
    clearAuthMessage();
}

// 显示认证消息
function showAuthMessage(message, isError = false) {
    const messageElement = document.getElementById('auth-message');
    messageElement.textContent = message;
    messageElement.className = 'auth-message ' + (isError ? 'error' : 'success');
}

// 清除认证消息
function clearAuthMessage() {
    const messageElement = document.getElementById('auth-message');
    messageElement.textContent = '';
    messageElement.className = 'auth-message';
}

// 注册用户
async function register() {
    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    
    if (!username || !email || !password) {
        showAuthMessage('请填写所有字段', true);
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, email, password })
        });
        
        const data = await response.json();
        if (response.ok) {
            showAuthMessage('注册成功，请登录');
            setTimeout(() => switchToLogin(), 1500);
        } else {
            showAuthMessage(data.error || '注册失败', true);
        }
    } catch (error) {
        // fallback到本地存储
        fallbackRegister(username, email, password);
    }
}

// 登录用户
async function login() {
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    
    if (!username || !password) {
        showAuthMessage('请填写用户名和密码', true);
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        if (response.ok) {
            // 保存登录状态
            localStorage.setItem('currentUser', JSON.stringify(data.user));
            
            // 切换到应用页面
            document.getElementById('auth-container').style.display = 'none';
            document.getElementById('app-container').style.display = 'block';
            document.getElementById('user-name').textContent = data.user.username;
            
            // 加载统计数据
            loadStats();
            // 加载历史记录
            loadHistory();
            // 加载主题设置
            loadThemeSettings();
        } else {
            showAuthMessage(data.error || '登录失败', true);
        }
    } catch (error) {
        // fallback到本地存储
        fallbackLogin(username, password);
    }
}

// 退出登录
function logout() {
    localStorage.removeItem('currentUser');
    document.getElementById('app-container').style.display = 'none';
    document.getElementById('auth-container').style.display = 'flex';
    switchToLogin();
}

// 检查登录状态
function checkLoginStatus() {
    const currentUser = localStorage.getItem('currentUser');
    if (currentUser) {
        const user = JSON.parse(currentUser);
        document.getElementById('auth-container').style.display = 'none';
        document.getElementById('app-container').style.display = 'block';
        document.getElementById('user-name').textContent = user.username;
        loadStats();
        loadHistory();
        loadThemeSettings();
    } else {
        document.getElementById('auth-container').style.display = 'flex';
        document.getElementById('app-container').style.display = 'none';
    }
}

// 本地存储fallback函数

function fallbackRegister(username, email, password) {
    try {
        // 检查用户是否已存在
        const users = JSON.parse(localStorage.getItem('users') || '[]');
        if (users.some(user => user.username === username)) {
            showAuthMessage('用户名已存在', true);
            return;
        }
        
        // 创建新用户
        const newUser = {
            id: Date.now().toString(),
            username,
            email,
            password,
            createdAt: new Date().toISOString()
        };
        
        users.push(newUser);
        localStorage.setItem('users', JSON.stringify(users));
        
        showAuthMessage('注册成功，请登录');
        setTimeout(() => switchToLogin(), 1500);
    } catch (error) {
        showAuthMessage('注册失败，请重试', true);
        console.error('注册错误:', error);
    }
}

function fallbackLogin(username, password) {
    try {
        const users = JSON.parse(localStorage.getItem('users') || '[]');
        const user = users.find(user => user.username === username && user.password === password);
        
        if (!user) {
            showAuthMessage('用户名或密码错误', true);
            return;
        }
        
        // 保存登录状态
        localStorage.setItem('currentUser', JSON.stringify(user));
        
        // 切换到应用页面
        document.getElementById('auth-container').style.display = 'none';
        document.getElementById('app-container').style.display = 'block';
        document.getElementById('user-name').textContent = user.username;
        
        loadStats();
        loadHistory();
        loadThemeSettings();
    } catch (error) {
        showAuthMessage('登录失败，请重试', true);
        console.error('登录错误:', error);
    }
}

// 论文检索功能
async function retrievePapers() {
    const query = document.getElementById('retrieve-query').value;
    const mode = document.getElementById('retrieve-mode').value;
    const topk = document.getElementById('retrieve-topk').value;
    
    if (!query) {
        document.getElementById('retrieve-results').innerHTML = '<div class="error-message">请输入检索查询内容</div>';
        return;
    }
    
    document.getElementById('retrieve-results').innerHTML = '<div class="loading">正在检索，请稍候...</div>';
    
    try {
        const response = await fetch(`${RETRIEVE_API_URL}/api/retrieve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                ranking_mode: mode,
                top_k: parseInt(topk)
            })
        });
        
        const data = await response.json();
        
        console.log('检索API返回:', data);
        
        if (data.success) {
            if (data.papers && data.papers.length > 0) {
                displayRetrieveResults(data.papers);
                saveHistory('retrieve', query, data.papers);
                updateStats('retrieve');
            } else {
                // 成功但无结果
                document.getElementById('retrieve-results').innerHTML = `<div class="info-message">${data.message || '未找到相关论文'}</div>`;
            }
        } else {
            document.getElementById('retrieve-results').innerHTML = `<div class="error-message">${data.message || '检索失败'}</div>`;
        }
    } catch (error) {
        console.error('检索错误:', error);
        document.getElementById('retrieve-results').innerHTML = `<div class="error-message">检索失败: ${error.message}<br>请确保检索API服务正在运行 (端口5002)</div>`;
    }
}

// 显示检索结果
function displayRetrieveResults(papers) {
    const resultsDiv = document.getElementById('retrieve-results');
    
    if (!papers || papers.length === 0) {
        resultsDiv.innerHTML = '<div class="info-message">未找到相关论文</div>';
        return;
    }
    
    let html = `<div class="results-header">共找到 ${papers.length} 篇相关论文</div>`;
    
    papers.forEach((paper, index) => {
        html += `
            <div class="paper-result">
                <div class="paper-number">${index + 1}</div>
                <div class="paper-details">
                    <div class="paper-title">${paper.title}</div>
                    <div class="paper-meta">
                        <span class="paper-year">年份: ${paper.year}</span>
                        <span class="paper-score">相关性: ${paper.relevance_score}</span>
                    </div>
                    <div class="paper-concepts">匹配概念: ${paper.matched_concepts.join(', ')}</div>
                    <div class="paper-url">
                        <a href="${paper.url}" target="_blank">查看论文</a>
                    </div>
                </div>
            </div>
        `;
    });
    
    resultsDiv.innerHTML = html;
}

// 论文总结功能
let uploadedPdfText = ''; // 保存上传PDF的文本

async function generateSummary() {
    const text = document.getElementById('summary-text').value;
    const type = document.getElementById('summary-type').value;
    const tokens = document.getElementById('summary-tokens').value;
    
    // 如果有上传的PDF内容，优先使用
    let inputText = uploadedPdfText || text;
    
    if (!inputText) {
        document.getElementById('summary-results').innerHTML = '<div class="error-message">请上传PDF文件或输入论文内容</div>';
        return;
    }
    
    document.getElementById('summary-results').innerHTML = '<div class="loading">正在生成总结，请稍候...</div>';
    
    try {
        const response = await fetch(`${SUMMARY_API_URL}/api/summary`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: inputText,
                type: type,
                max_tokens: parseInt(tokens)
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            displaySummaryResults(data.summary);
            saveHistory('summary', inputText.substring(0, 100), data.summary);
            updateStats('summary');
        } else {
            document.getElementById('summary-results').innerHTML = `<div class="error-message">${data.message}</div>`;
        }
    } catch (error) {
        console.error('总结错误:', error);
        document.getElementById('summary-results').innerHTML = `<div class="error-message">总结失败: ${error.message}<br>请确保总结API服务正在运行 (端口5001)</div>`;
    }
}

// PDF文件处理
async function handlePdfFile(file) {
    if (!file || file.type !== 'application/pdf') {
        alert('请选择PDF文件');
        return;
    }
    
    // 显示文件信息
    document.getElementById('file-name').textContent = file.name;
    document.getElementById('file-size').textContent = formatFileSize(file.size);
    document.querySelector('.upload-content').style.display = 'none';
    document.getElementById('file-info').style.display = 'flex';
    
    // 显示加载状态
    document.getElementById('summary-results').innerHTML = `
        <div class="pdf-loading">
            <span class="spinner"></span>
            正在提取PDF内容，请稍候...
        </div>
    `;
    
    try {
        const arrayBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        
        let fullText = '';
        const totalPages = pdf.numPages;
        
        // 逐页提取文本
        for (let i = 1; i <= totalPages; i++) {
            const page = await pdf.getPage(i);
            const textContent = await page.getTextContent();
            const pageText = textContent.items.map(item => item.str).join(' ');
            fullText += pageText + '\n\n';
            
            // 更新进度
            document.getElementById('summary-results').innerHTML = `
                <div class="pdf-loading">
                    <span class="spinner"></span>
                    正在提取PDF内容... (${i}/${totalPages})
                </div>
            `;
        }
        
        // 保存提取的文本
        uploadedPdfText = fullText;
        
        // 将文本填入textarea
        document.getElementById('summary-text').value = fullText.substring(0, 5000) + (fullText.length > 5000 ? '\n\n[内容过长，已截断前5000字符]' : '');
        
        document.getElementById('summary-results').innerHTML = `
            <div class="success-message">
                PDF内容提取成功！共 ${totalPages} 页，已提取 ${fullText.length} 个字符
            </div>
        `;
        
    } catch (error) {
        console.error('PDF解析错误:', error);
        document.getElementById('summary-results').innerHTML = `
            <div class="error-message">
                PDF解析失败: ${error.message}<br>
                提示：请确保PDF包含可提取的文本内容
            </div>
        `;
        removeFile();
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function removeFile() {
    uploadedPdfText = '';
    document.getElementById('pdf-file-input').value = '';
    document.getElementById('file-name').textContent = '';
    document.getElementById('file-size').textContent = '';
    document.querySelector('.upload-content').style.display = 'flex';
    document.getElementById('file-info').style.display = 'none';
    document.getElementById('summary-text').value = '';
}

// 文件上传事件监听
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('pdf-file-input');
    const uploadArea = document.getElementById('upload-area');
    
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                handlePdfFile(e.target.files[0]);
            }
        });
    }
    
    // 拖拽上传
    if (uploadArea) {
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', function(e) {
            e.preventDefault();
            this.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].type === 'application/pdf') {
                handlePdfFile(files[0]);
            } else {
                alert('请拖拽PDF文件');
            }
        });
    }
    
    checkLoginStatus();
});

// 显示总结结果
function displaySummaryResults(summary) {
    const resultsDiv = document.getElementById('summary-results');
    resultsDiv.innerHTML = `<div class="summary-content">${marked.parse(summary)}</div>`;
}

// 论文翻译功能（暂时空着）
async function translateText() {
    const text = document.getElementById('translate-text').value;
    const source = document.getElementById('translate-source').value;
    const target = document.getElementById('translate-target').value;
    
    if (!text) {
        document.getElementById('translate-results').innerHTML = '<div class="error-message">请输入翻译内容</div>';
        return;
    }
    
    document.getElementById('translate-results').innerHTML = '<div class="info-message">翻译功能暂未开放，API服务正在开发中</div>';
    
    // 保存历史记录
    saveHistory('translate', text, '翻译功能暂未开放');
}

// 综述生成功能（暂时空着）
async function generateReview() {
    const topic = document.getElementById('review-topic').value;
    const papers = document.getElementById('review-papers').value;
    
    if (!topic || !papers) {
        document.getElementById('review-results').innerHTML = '<div class="error-message">请输入研究主题和论文内容</div>';
        return;
    }
    
    document.getElementById('review-results').innerHTML = '<div class="info-message">综述生成功能暂未开放，API服务正在开发中</div>';
    
    // 保存历史记录
    saveHistory('review', topic, '综述生成功能暂未开放');
}

// 清空输入函数
function clearRetrieveInput() {
    document.getElementById('retrieve-query').value = '';
    document.getElementById('retrieve-results').innerHTML = '';
}

function clearSummaryInput() {
    document.getElementById('summary-text').value = '';
    document.getElementById('summary-results').innerHTML = '';
    removeFile();
}

function clearTranslateInput() {
    document.getElementById('translate-text').value = '';
    document.getElementById('translate-results').innerHTML = '';
}

function clearReviewInput() {
    document.getElementById('review-topic').value = '';
    document.getElementById('review-papers').value = '';
    document.getElementById('review-results').innerHTML = '';
}

// 统计数据管理
function loadStats() {
    const currentUser = localStorage.getItem('currentUser');
    if (!currentUser) return;
    
    const user = JSON.parse(currentUser);
    const stats = JSON.parse(localStorage.getItem(`stats_${user.id}`) || '{"retrieve":0,"summary":0,"translate":0,"review":0}');
    
    document.getElementById('total-retrievals').textContent = stats.retrieve;
    document.getElementById('total-summaries').textContent = stats.summary;
    document.getElementById('total-translations').textContent = stats.translate;
    document.getElementById('total-reviews').textContent = stats.review;
}

function updateStats(type) {
    const currentUser = localStorage.getItem('currentUser');
    if (!currentUser) return;
    
    const user = JSON.parse(currentUser);
    const stats = JSON.parse(localStorage.getItem(`stats_${user.id}`) || '{"retrieve":0,"summary":0,"translate":0,"review":0}');
    
    stats[type] = (stats[type] || 0) + 1;
    localStorage.setItem(`stats_${user.id}`, JSON.stringify(stats));
    
    loadStats();
}

// 历史记录管理
function saveHistory(type, input, output) {
    const currentUser = localStorage.getItem('currentUser');
    if (!currentUser) return;
    
    const user = JSON.parse(currentUser);
    const history = JSON.parse(localStorage.getItem(`history_${user.id}`) || '[]');
    
    history.unshift({
        type: type,
        input: input.substring(0, 100), // 只保存前100个字符
        output: typeof output === 'string' ? output.substring(0, 200) : JSON.stringify(output).substring(0, 200),
        timestamp: new Date().toISOString()
    });
    
    // 最多保存50条历史记录
    if (history.length > 50) {
        history.splice(50);
    }
    
    localStorage.setItem(`history_${user.id}`, JSON.stringify(history));
}

function loadHistory() {
    const currentUser = localStorage.getItem('currentUser');
    if (!currentUser) return;
    
    const user = JSON.parse(currentUser);
    const history = JSON.parse(localStorage.getItem(`history_${user.id}`) || '[]');
    
    displayHistory(history);
}

function displayHistory(history) {
    const historyList = document.getElementById('history-list');
    
    if (!history || history.length === 0) {
        historyList.innerHTML = '<div class="info-message">暂无历史记录</div>';
        return;
    }
    
    let html = '';
    
    history.forEach(item => {
        const typeNames = {
            'retrieve': '论文检索',
            'summary': '论文总结',
            'translate': '论文翻译',
            'review': '综述生成'
        };
        
        html += `
            <div class="history-item">
                <div class="history-header">
                    <span class="history-type">${typeNames[item.type] || item.type}</span>
                    <span class="history-time">${formatTime(item.timestamp)}</span>
                </div>
                <div class="history-content">
                    <p class="history-input">输入: ${item.input}</p>
                    <p class="history-output">输出: ${item.output}</p>
                </div>
            </div>
        `;
    });
    
    historyList.innerHTML = html;
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN');
}

function clearHistory() {
    const currentUser = localStorage.getItem('currentUser');
    if (!currentUser) return;
    
    const user = JSON.parse(currentUser);
    localStorage.removeItem(`history_${user.id}`);
    loadHistory();
}

// 个人主页信息加载
function loadProfileInfo() {
    const currentUser = localStorage.getItem('currentUser');
    if (!currentUser) return;
    
    const user = JSON.parse(currentUser);
    document.getElementById('profile-username').value = user.username;
    document.getElementById('profile-email').value = user.email || '';
}

// 主题设置功能
function loadThemeSettings() {
    const currentUser = localStorage.getItem('currentUser');
    if (!currentUser) return;
    
    const user = JSON.parse(currentUser);
    const settings = JSON.parse(localStorage.getItem(`theme_${user.id}`) || '{}');
    
    if (settings.theme) {
        document.getElementById('settings-theme').value = settings.theme;
    }
    if (settings.primaryColor) {
        document.getElementById('settings-primary-color').value = settings.primaryColor;
    }
    if (settings.secondaryColor) {
        document.getElementById('settings-secondary-color').value = settings.secondaryColor;
    }
    
    applyTheme(settings);
}

function previewTheme() {
    const theme = document.getElementById('settings-theme').value;
    const primaryColor = document.getElementById('settings-primary-color').value;
    const secondaryColor = document.getElementById('settings-secondary-color').value;
    
    const settings = {
        theme,
        primaryColor,
        secondaryColor
    };
    
    applyTheme(settings);
}

function applyTheme(settings) {
    const root = document.documentElement;
    
    // 应用深色/浅色主题
    if (settings.theme === 'dark') {
        document.body.classList.add('dark-theme');
    } else {
        document.body.classList.remove('dark-theme');
    }
    
    // 应用自定义颜色
    if (settings.primaryColor) {
        root.style.setProperty('--primary-color', settings.primaryColor);
        root.style.setProperty('--accent-color', settings.primaryColor);
    }
    if (settings.secondaryColor) {
        root.style.setProperty('--secondary-color', settings.secondaryColor);
    }
    if (settings.primaryColor && settings.secondaryColor) {
        root.style.setProperty('--button-gradient', `linear-gradient(135deg, ${settings.primaryColor}, ${settings.secondaryColor})`);
    }
}

function saveAppSettings() {
    const currentUser = localStorage.getItem('currentUser');
    if (!currentUser) return;
    
    const user = JSON.parse(currentUser);
    
    const settings = {
        theme: document.getElementById('settings-theme').value,
        primaryColor: document.getElementById('settings-primary-color').value,
        secondaryColor: document.getElementById('settings-secondary-color').value
    };
    
    localStorage.setItem(`theme_${user.id}`, JSON.stringify(settings));
    applyTheme(settings);
    
    alert('设置已保存');
}