import client from "../client";
import type {
  ResumeBasics,
  ResumeBasicsCreate,
  ResumeBasicsUpdate,
  ResumeSkillGroup,
  ResumeSkillGroupCreate,
  ResumeSkillGroupUpdate,
  ResumeExperience,
  ResumeExperienceCreate,
  ResumeExperienceUpdate,
  PaginatedResponse,
} from "@/types/models";

// --- Basics ---
export async function listResumeBasics(params?: { page?: number }): Promise<PaginatedResponse<ResumeBasics>> {
  const res = await client.get("/resume/basics/", { params });
  return res.data;
}

export async function getResumeBasics(id: string): Promise<ResumeBasics> {
  const res = await client.get(`/resume/basics/${id}`);
  return res.data;
}

export async function createResumeBasics(data: ResumeBasicsCreate): Promise<ResumeBasics> {
  const res = await client.post("/resume/basics/", data);
  return res.data;
}

export async function updateResumeBasics(id: string, data: ResumeBasicsUpdate): Promise<ResumeBasics> {
  const res = await client.put(`/resume/basics/${id}`, data);
  return res.data;
}

export async function deleteResumeBasics(id: string): Promise<void> {
  await client.delete(`/resume/basics/${id}`);
}

// --- Skills ---
export async function listResumeSkills(params?: { page?: number }): Promise<PaginatedResponse<ResumeSkillGroup>> {
  const res = await client.get("/resume/skills/", { params });
  return res.data;
}

export async function createResumeSkill(data: ResumeSkillGroupCreate): Promise<ResumeSkillGroup> {
  const res = await client.post("/resume/skills/", data);
  return res.data;
}

export async function updateResumeSkill(id: string, data: ResumeSkillGroupUpdate): Promise<ResumeSkillGroup> {
  const res = await client.put(`/resume/skills/${id}`, data);
  return res.data;
}

export async function deleteResumeSkill(id: string): Promise<void> {
  await client.delete(`/resume/skills/${id}`);
}

// --- Experiences ---
export async function listResumeExperiences(params?: { page?: number }): Promise<PaginatedResponse<ResumeExperience>> {
  const res = await client.get("/resume/experiences/", { params });
  return res.data;
}

export async function createResumeExperience(data: ResumeExperienceCreate): Promise<ResumeExperience> {
  const res = await client.post("/resume/experiences/", data);
  return res.data;
}

export async function updateResumeExperience(id: string, data: ResumeExperienceUpdate): Promise<ResumeExperience> {
  const res = await client.put(`/resume/experiences/${id}`, data);
  return res.data;
}

export async function deleteResumeExperience(id: string): Promise<void> {
  await client.delete(`/resume/experiences/${id}`);
}
