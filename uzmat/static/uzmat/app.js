// Photo upload preview for create ad page - МНОЖЕСТВЕННЫЕ ИЗОБРАЖЕНИЯ (до 10)
(() => {
  const photoUpload = document.getElementById('photo-upload');
  const photoPreview = document.getElementById('photo-preview');
  
  if (!photoUpload || !photoPreview) return;

  let selectedFiles = [];
  // Делаем selectedFiles доступным глобально для исправления проблемы с FormData
  window.selectedFiles = selectedFiles;

  // Обработчик выбора файлов - множественный выбор
  photoUpload.addEventListener('change', (e) => {
    const files = Array.from(e.target.files);
    
    if (files.length > 0) {
      // Проверяем общее количество файлов (максимум 10)
      const totalFiles = selectedFiles.length + files.length;
      if (totalFiles > 10) {
        alert('Можно загрузить максимум 10 фотографий. Вы уже выбрали ' + selectedFiles.length + ' фото.');
        photoUpload.value = '';
        return;
      }
      
      // Проверяем каждый файл
      const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10 МБ
      const validFiles = [];
      for (const file of files) {
        // Проверяем тип файла
        if (!file.type.startsWith('image/')) {
          alert('Файл "' + file.name + '" не является изображением. Пропущен.');
          continue;
        }
        
        // Проверяем размер файла
        if (file.size > MAX_IMAGE_SIZE) {
          const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
          alert('Файл "' + file.name + '" слишком большой (' + sizeMB + ' МБ). Максимальный размер: 10 МБ. Файл пропущен.');
          continue;
        }
        
        validFiles.push(file);
      }
      
      // Добавляем валидные файлы
      selectedFiles = selectedFiles.concat(validFiles);
      window.selectedFiles = selectedFiles; // Обновляем глобальную переменную
      
      // Обновляем input для сохранения всех выбранных файлов
      updateFileInput();
      renderPhotoPreview();
    }
  });

  function updateFileInput() {
    // Создаем новый DataTransfer для сохранения всех файлов
    const dt = new DataTransfer();
    selectedFiles.forEach(file => dt.items.add(file));
    photoUpload.files = dt.files;
  }

  function renderPhotoPreview() {
    photoPreview.innerHTML = '';
    
    if (selectedFiles.length > 0) {
      selectedFiles.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'uz-photo-preview-item';
        item.style.cssText = 'position: relative; display: inline-block; margin: 8px;';
        
        const img = document.createElement('img');
        img.style.cssText = 'width: 200px; height: 150px; object-fit: cover; border-radius: 8px; border: 2px solid var(--uz-border);';
        const reader = new FileReader();
        reader.onload = (event) => {
          img.src = event.target.result;
        };
        reader.readAsDataURL(file);
        img.alt = 'Предпросмотр фото ' + (index + 1);
        
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'uz-photo-preview-item-remove';
        removeBtn.setAttribute('aria-label', 'Удалить фото');
        removeBtn.innerHTML = '×';
        removeBtn.style.cssText = 'position: absolute; top: 4px; right: 4px; width: 32px; height: 32px; border-radius: 50%; background: rgba(239, 68, 68, 0.95); color: white; border: 2px solid white; cursor: pointer; font-size: 22px; font-weight: bold; line-height: 1; display: flex; align-items: center; justify-content: center; z-index: 10; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3); transition: all 0.2s;';
        removeBtn.onmouseover = function() { 
          this.style.background = 'rgba(239, 68, 68, 1)'; 
          this.style.transform = 'scale(1.1)';
        };
        removeBtn.onmouseout = function() { 
          this.style.background = 'rgba(239, 68, 68, 0.95)'; 
          this.style.transform = 'scale(1)';
        };
        removeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          selectedFiles.splice(index, 1);
          window.selectedFiles = selectedFiles; // Обновляем глобальную переменную
          updateFileInput();
          renderPhotoPreview();
        });
        
        item.appendChild(img);
        item.appendChild(removeBtn);
        photoPreview.appendChild(item);
      });
    }
  }

  // Drag and drop
  const uploadArea = photoUpload.closest('.uz-upload-area');
  if (uploadArea) {
    const uploadButton = uploadArea.querySelector('.uz-upload-button');
    
    uploadArea.addEventListener('dragover', (e) => {
      e.preventDefault();
      if (uploadButton) {
        uploadButton.style.borderColor = 'var(--uz-primary)';
        uploadButton.style.background = 'var(--uz-primary-alpha)';
      }
    });

    uploadArea.addEventListener('dragleave', () => {
      if (uploadButton) {
        uploadButton.style.borderColor = '';
        uploadButton.style.background = '';
      }
    });

    uploadArea.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (uploadButton) {
        uploadButton.style.borderColor = '';
        uploadButton.style.background = '';
      }
      
      const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
      if (files.length > 0) {
        // Проверяем общее количество файлов (максимум 10)
        const totalFiles = selectedFiles.length + files.length;
        if (totalFiles > 10) {
          alert('Можно загрузить максимум 10 фотографий. Вы уже выбрали ' + selectedFiles.length + ' фото.');
          return;
        }
        
        // Проверяем размер каждого файла
        const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10 МБ
        const validFiles = [];
        for (const file of files) {
          // Проверяем размер файла
          if (file.size > MAX_IMAGE_SIZE) {
            const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
            alert('Файл "' + file.name + '" слишком большой (' + sizeMB + ' МБ). Максимальный размер: 10 МБ. Файл пропущен.');
            continue;
          }
          validFiles.push(file);
        }
        
        // Добавляем только валидные файлы
        if (validFiles.length > 0) {
          selectedFiles = selectedFiles.concat(validFiles);
          window.selectedFiles = selectedFiles; // Обновляем глобальную переменную
          updateFileInput();
          renderPhotoPreview();
          console.log('Файлы добавлены через drag-and-drop:', validFiles.length);
        }
      }
    });
  }
})();

// Theme toggle functionality
(function() {
  // Функция для получения текущей темы
  function getTheme() {
    return localStorage.getItem('theme') || 'dark';
  }

  // Функция для установки темы
  function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }

  // Функция для переключения темы
  function toggleTheme() {
    const currentTheme = getTheme();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
  }

  // Инициализация темы при загрузке страницы
  function initTheme() {
    const savedTheme = getTheme();
    setTheme(savedTheme);
  }

  // Обработчик клика на кнопки переключения темы
  function initThemeToggle() {
    const themeToggleButtons = document.querySelectorAll('[data-theme-toggle]');
    themeToggleButtons.forEach(button => {
      button.addEventListener('click', (e) => {
        e.preventDefault();
        toggleTheme();
      });
    });
  }

  // Инициализация при загрузке DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initTheme();
      initThemeToggle();
    });
  } else {
    initTheme();
    initThemeToggle();
  }
})();

// Toast Notifications System
(function() {
  // Функция для создания и отображения toast-уведомления
  window.showToast = function(message, type = 'info', duration = 5000) {
    const container = document.getElementById('uz-toast-container');
    if (!container) {
      console.warn('Toast container not found');
      return;
    }

    // Определяем тип и иконку
    const typeConfig = {
      success: {
        class: 'uz-toast--success',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        title: 'Успешно'
      },
      error: {
        class: 'uz-toast--error',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>',
        title: 'Ошибка'
      },
      warning: {
        class: 'uz-toast--warning',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
        title: 'Внимание'
      },
      info: {
        class: 'uz-toast--info',
        icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>',
        title: 'Информация'
      }
    };

    const config = typeConfig[type] || typeConfig.info;

    // Создаем элемент toast
    const toast = document.createElement('div');
    toast.className = `uz-toast ${config.class}`;
    
    toast.innerHTML = `
      <div class="uz-toast-icon">${config.icon}</div>
      <div class="uz-toast-content">
        <div class="uz-toast-title">${config.title}</div>
        <div class="uz-toast-message">${message}</div>
      </div>
      <button class="uz-toast-close" aria-label="Закрыть">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    `;

    // Добавляем в контейнер
    container.appendChild(toast);

    // Функция закрытия
    const closeToast = () => {
      toast.classList.add('uz-toast--exiting');
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 300);
    };

    // Обработчик кнопки закрытия
    const closeBtn = toast.querySelector('.uz-toast-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeToast);
    }

    // Автоматическое закрытие
    if (duration > 0) {
      setTimeout(closeToast, duration);
    }

    return toast;
  };

  // Обработка Django messages при загрузке страницы
  function initDjangoMessages() {
    // Ищем элементы с сообщениями Django (если они есть в шаблоне)
    const messageElements = document.querySelectorAll('[data-django-message]');
    messageElements.forEach(element => {
      const message = element.textContent.trim();
      const messageType = element.getAttribute('data-django-message') || 'info';
      if (message) {
        window.showToast(message, messageType);
        // Удаляем элемент после показа
        element.remove();
      }
    });

    // Также проверяем старые алерты и конвертируем их в toast
    const alertElements = document.querySelectorAll('.uz-alert');
    alertElements.forEach(alert => {
      const message = alert.textContent.trim();
      if (message) {
        // Определяем тип по классам или стилям
        let type = 'info';
        if (alert.style.color && alert.style.color.includes('239, 68, 68')) {
          type = 'error';
        } else if (alert.style.color && alert.style.color.includes('16, 185, 129')) {
          type = 'success';
        } else if (alert.style.color && alert.style.color.includes('245, 158, 11')) {
          type = 'warning';
        }
        
        window.showToast(message, type);
        // Удаляем старый алерт
        setTimeout(() => {
          if (alert.parentNode) {
            alert.parentNode.removeChild(alert);
          }
        }, 100);
      }
    });
  }

  // Инициализация при загрузке DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDjangoMessages);
  } else {
    initDjangoMessages();
  }
})();

// Универсальная обработка уведомлений из sessionStorage (работает на всех страницах)
(function() {
  function showNotificationFromStorage() {
    const savedNotification = sessionStorage.getItem('ad_created_notification');
    if (savedNotification) {
      try {
        const notification = JSON.parse(savedNotification);
        // Ждем, пока showToast и контейнер будут доступны
        const checkInterval = setInterval(function() {
          if (window.showToast && document.getElementById('uz-toast-container')) {
            clearInterval(checkInterval);
            // Показываем уведомление с длительностью 5 секунд
            window.showToast(notification.message, notification.type || 'success', 5000);
            // Удаляем уведомление из sessionStorage после показа
            sessionStorage.removeItem('ad_created_notification');
          }
        }, 50); // Проверяем каждые 50мс
        
        // Таймаут на случай, если showToast не загрузится за 5 секунд
        setTimeout(function() {
          clearInterval(checkInterval);
          sessionStorage.removeItem('ad_created_notification');
        }, 5000);
      } catch (e) {
        console.error('Ошибка при обработке уведомления из sessionStorage:', e);
        sessionStorage.removeItem('ad_created_notification');
      }
    }
  }
  
  // Пытаемся показать уведомление как можно раньше
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', showNotificationFromStorage);
  } else {
    // DOM уже загружен, но showToast может еще не быть доступен
    showNotificationFromStorage();
  }
})();

// Price filter helper: "!" tooltip + require country before enabling price_from/price_to (global, all pages)
(function() {
  function closeAllTooltips(root = document) {
    root.querySelectorAll('[data-price-help-tooltip]').forEach((t) => t.setAttribute('hidden', ''));
  }

  function updatePriceControls(root = document) {
    const forms = Array.from(root.querySelectorAll('form'));
    forms.forEach((form) => {
      const countryInput = form.querySelector('input[name="country"]');
      const priceFrom = form.querySelector('input[name="price_from"]');
      const priceTo = form.querySelector('input[name="price_to"]');
      const helpBtn = form.querySelector('[data-price-help-toggle]');
      const tooltip = form.querySelector('[data-price-help-tooltip]');

      if (!countryInput || (!priceFrom && !priceTo) || !helpBtn || !tooltip) return;

      const hasCountry = !!(countryInput.value || '').trim();

      if (priceFrom) priceFrom.disabled = !hasCountry;
      if (priceTo) priceTo.disabled = !hasCountry;

      // Подсказка нужна только когда страна не выбрана
      helpBtn.disabled = hasCountry;
      if (hasCountry) tooltip.setAttribute('hidden', '');
    });
  }

  function init() {
    updatePriceControls(document);

    document.addEventListener('click', (e) => {
      const btn = e.target && e.target.closest && e.target.closest('[data-price-help-toggle]');
      if (btn) {
        e.preventDefault();
        e.stopPropagation();
        if (btn.disabled) return;
        const form = btn.closest('form') || document;
        const tooltip = form.querySelector('[data-price-help-tooltip]');
        if (!tooltip) return;
        const isHidden = tooltip.hasAttribute('hidden');
        closeAllTooltips(document);
        if (isHidden) tooltip.removeAttribute('hidden');
        return;
      }

      // клик вне тултипа закрывает его
      if (!e.target.closest('[data-price-help-tooltip]')) {
        closeAllTooltips(document);
      }

      // выбор страны через кнопки фильтров
      const countryBtn = e.target && e.target.closest && e.target.closest('[data-filter-name="country"]');
      if (countryBtn) {
        setTimeout(() => updatePriceControls(document), 0);
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeAllTooltips(document);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

// Burger Menu
(() => {
  const burgerBtn = document.getElementById('burger-menu-btn');
  const burgerMenu = document.getElementById('burger-menu');
  const burgerOverlay = document.getElementById('burger-menu-overlay');
  const burgerClose = document.getElementById('burger-menu-close');

  if (!burgerBtn || !burgerMenu || !burgerOverlay || !burgerClose) return;

  function openMenu() {
    burgerMenu.classList.add('active');
    burgerOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeMenu() {
    burgerMenu.classList.remove('active');
    burgerOverlay.classList.remove('active');
    document.body.style.overflow = '';
  }

  burgerBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    openMenu();
  });

  burgerClose.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    closeMenu();
  });

  burgerOverlay.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    closeMenu();
  });

  // Закрытие по Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && burgerMenu.classList.contains('active')) {
      closeMenu();
    }
  });

  // Закрытие при клике на ссылку в меню
  const menuLinks = burgerMenu.querySelectorAll('a');
  menuLinks.forEach(link => {
    link.addEventListener('click', () => {
      closeMenu();
    });
  });
})();

