class ProgressTracker {
    constructor() {
        this.stages = [
            { id: 'validation', name: 'Validating Input', duration: 500 },
            { id: 'personas', name: 'Generating Expert Personas', duration: 8000 },
            { id: 'analysis', name: 'Expert Analysis in Progress', duration: 15000 },
            { id: 'synthesis', name: 'Synthesizing Results', duration: 8000 },
            { id: 'formatting', name: 'Formatting Report', duration: 2000 }
        ];
        this.currentStage = 0;
        this.startTime = null;
    }

    start() {
        this.startTime = Date.now();
        this.currentStage = 0;
        this.updateProgress();
    }

    nextStage() {
        if (this.currentStage < this.stages.length - 1) {
            this.currentStage++;
            this.updateProgress();
        }
    }

    updateProgress() {
        const stage = this.stages[this.currentStage];
        const progressPercent = ((this.currentStage + 1) / this.stages.length) * 100;
        
        document.getElementById('current-stage').textContent = stage.name;
        document.getElementById('progress-bar').style.width = `${progressPercent}%`;
        document.getElementById('stage-counter').textContent = `${this.currentStage + 1} of ${this.stages.length}`;
        
        // Add estimated time remaining
        if (this.startTime) {
            const elapsed = Date.now() - this.startTime;
            const totalEstimated = this.stages.reduce((sum, s) => sum + s.duration, 0);
            const remaining = Math.max(0, totalEstimated - elapsed);
            document.getElementById('time-remaining').textContent = `~${Math.ceil(remaining / 1000)}s remaining`;
        }
    }

    complete() {
        document.getElementById('current-stage').textContent = 'Analysis Complete!';
        document.getElementById('progress-bar').style.width = '100%';
        document.getElementById('time-remaining').textContent = 'Done';
    }

    error(message) {
        document.getElementById('current-stage').textContent = `Error: ${message}`;
        document.getElementById('progress-bar').style.backgroundColor = '#e74c3c';
    }
}

// Enhanced error handling
class ErrorHandler {
    static show(message, type = 'error') {
        const errorDiv = document.createElement('div');
        errorDiv.className = `alert alert-${type}`;
        errorDiv.innerHTML = `
            <span class="alert-icon">⚠️</span>
            <span class="alert-message">${message}</span>
            <button class="alert-close" onclick="this.parentElement.remove()">×</button>
        `;
        
        document.querySelector('.container').insertBefore(errorDiv, document.querySelector('.input-section'));
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentElement) {
                errorDiv.remove();
            }
        }, 5000);
    }

    static clear() {
        document.querySelectorAll('.alert').forEach(alert => alert.remove());
    }
} 