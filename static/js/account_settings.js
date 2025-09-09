// Account Settings JavaScript - Optimized
document.addEventListener('DOMContentLoaded', function() {
    // Avatar handling
    const avatarInput = document.getElementById('id_avatar');
    const avatarPreview = document.getElementById('avatar-preview');
    const removeAvatarCheckbox = document.getElementById('remove_avatar');
    const removeAvatarSection = document.querySelector('.remove-avatar-section');
    
    if (avatarInput && avatarPreview) {
        avatarInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    avatarPreview.innerHTML = `<img src="${e.target.result}" alt="Avatar Preview">`;
                };
                reader.readAsDataURL(file);
            }
        });
    }
    
    // Remove avatar functionality
    if (removeAvatarCheckbox && removeAvatarSection) {
        const removeBtn = document.querySelector('.btn-remove-avatar');
        
        if (removeBtn) {
            removeBtn.addEventListener('click', function(e) {
                e.preventDefault();
                removeAvatarCheckbox.checked = !removeAvatarCheckbox.checked;
                updateRemoveAvatarUI();
            });
        }
        
        function updateRemoveAvatarUI() {
            if (removeAvatarCheckbox.checked) {
                removeBtn.style.background = 'linear-gradient(135deg, #22c55e, #16a34a)';
                removeBtn.innerHTML = '✓ تم تحديد الحذف';
            } else {
                removeBtn.style.background = 'linear-gradient(135deg, #ef4444, #dc2626)';
                removeBtn.innerHTML = '🗑️ حذف الصورة';
            }
        }
    }
    
    // Skin selection
    const skinOptions = document.querySelectorAll('.skin-option');
    skinOptions.forEach(option => {
        const radio = option.querySelector('input[type="radio"]');
        if (radio) {
            option.addEventListener('click', function() {
                // Remove selected class from all options
                skinOptions.forEach(opt => opt.classList.remove('selected'));
                // Add selected class to clicked option
                option.classList.add('selected');
                // Check the radio button
                radio.checked = true;
            });
            
            // Update UI on page load
            if (radio.checked) {
                option.classList.add('selected');
            }
        }
    });
    
    // Form validation
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '⏳ جاري الحفظ...';
            }
        });
    }
    
    // Auto-hide messages
    const messages = document.querySelectorAll('.alert');
    messages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            message.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                message.remove();
            }, 300);
        }, 5000);
    });
});
