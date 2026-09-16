document.addEventListener('DOMContentLoaded', function() {
    function setupSelectAll(selectAllId, permClass) {
        const selectAllCheckbox = document.getElementById(selectAllId);
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function() {
                const permCheckboxes = document.querySelectorAll(`.${permClass}`);
                permCheckboxes.forEach(checkbox => {
                    checkbox.checked = this.checked;
                });
            });
        }
    }

    setupSelectAll('select-all-view', 'view-perm');
    setupSelectAll('select-all-add', 'add-perm');
    setupSelectAll('select-all-change', 'change-perm');
    setupSelectAll('select-all-delete', 'delete-perm');
});